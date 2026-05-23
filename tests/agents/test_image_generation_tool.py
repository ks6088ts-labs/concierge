from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

from concierge.agents.infrastructure.tools import ImageGenerationError, generate_image


@pytest.mark.anyio
async def test_generate_image_calls_client_with_expected_arguments() -> None:
    mock_generate = Mock(
        return_value=SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(b"png-bytes").decode("utf-8"), revised_prompt="revised")]
        )
    )
    client: Any = SimpleNamespace(images=SimpleNamespace(generate=mock_generate))

    result = await generate_image(
        "A cat",
        size="1024x1024",
        n=1,
        client=client,
        model="gpt-image-2-deployment",
    )

    assert result.model == "gpt-image-2-deployment"
    assert result.size == "1024x1024"
    assert len(result.images) == 1
    assert result.images[0].revised_prompt == "revised"
    mock_generate.assert_called_once_with(
        model="gpt-image-2-deployment",
        prompt="A cat",
        size="1024x1024",
        n=1,
        response_format="b64_json",
    )


@pytest.mark.anyio
async def test_generate_image_writes_png_when_save_dir_is_provided(tmp_path) -> None:
    png_b64 = base64.b64encode(b"fake-png").decode("utf-8")
    client: Any = SimpleNamespace(
        images=SimpleNamespace(generate=Mock(return_value=SimpleNamespace(data=[SimpleNamespace(b64_json=png_b64)])))
    )

    result = await generate_image("A cat", save_dir=str(tmp_path), client=client, model="gpt-image-2")

    assert len(result.images) == 1
    saved_path = result.images[0].path
    assert saved_path is not None
    assert saved_path.endswith(".png")
    assert tmp_path.resolve() in Path(saved_path).resolve().parents
    assert Path(saved_path).read_bytes() == b"fake-png"


@pytest.mark.anyio
async def test_generate_image_rejects_invalid_size() -> None:
    with pytest.raises(ValueError, match="size must be one of"):
        await generate_image("A cat", size="800x800")


@pytest.mark.anyio
@pytest.mark.parametrize("n", [0, 11])
async def test_generate_image_rejects_invalid_n(n: int) -> None:
    with pytest.raises(ValueError, match="n must be between 1 and 10"):
        await generate_image("A cat", n=n)


@pytest.mark.anyio
async def test_generate_image_wraps_client_errors() -> None:
    client: Any = SimpleNamespace(images=SimpleNamespace(generate=Mock(side_effect=RuntimeError("boom"))))

    with pytest.raises(ImageGenerationError, match="failed to generate image"):
        await generate_image("A cat", client=client, model="gpt-image-2")


@pytest.mark.anyio
async def test_generate_image_wraps_processing_errors() -> None:
    client: Any = SimpleNamespace(
        images=SimpleNamespace(
            generate=Mock(
                return_value=SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(b"x").decode())])
            )
        )
    )

    with patch(
        "concierge.agents.infrastructure.tools.image_generation._write_png",
        side_effect=RuntimeError("write failure"),
    ):
        with pytest.raises(ImageGenerationError, match="failed to process generated image"):
            await generate_image("A cat", save_dir="/tmp", client=client, model="gpt-image-2")


def test_build_default_client_prefers_image_endpoint() -> None:
    """``AZURE_AI_PROJECT_ENDPOINT_IMAGE`` should override the shared endpoint."""
    from concierge.agents.infrastructure.tools import image_generation

    captured: dict[str, Any] = {}

    def _fake_azure_openai(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(**kwargs)

    with patch.object(image_generation, "AzureOpenAI", side_effect=_fake_azure_openai):
        with patch.object(image_generation, "DefaultAzureCredential", return_value=object()):
            with patch.object(image_generation, "get_bearer_token_provider", return_value=lambda: "tok"):
                with patch.object(
                    image_generation,
                    "get_microsoft_foundry_settings",
                    return_value=SimpleNamespace(
                        azure_ai_project_endpoint="https://shared.example/api/projects/p",
                        azure_ai_project_endpoint_image="https://image.example/api/projects/p",
                    ),
                ):
                    image_generation._build_default_client()

    assert captured["azure_endpoint"] == "https://image.example/api/projects/p"


def test_build_default_client_falls_back_to_shared_endpoint() -> None:
    """When ``AZURE_AI_PROJECT_ENDPOINT_IMAGE`` is empty, the shared endpoint is used."""
    from concierge.agents.infrastructure.tools import image_generation

    captured: dict[str, Any] = {}

    def _fake_azure_openai(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(**kwargs)

    with patch.object(image_generation, "AzureOpenAI", side_effect=_fake_azure_openai):
        with patch.object(image_generation, "DefaultAzureCredential", return_value=object()):
            with patch.object(image_generation, "get_bearer_token_provider", return_value=lambda: "tok"):
                with patch.object(
                    image_generation,
                    "get_microsoft_foundry_settings",
                    return_value=SimpleNamespace(
                        azure_ai_project_endpoint="https://shared.example/api/projects/p",
                        azure_ai_project_endpoint_image="",
                    ),
                ):
                    image_generation._build_default_client()

    assert captured["azure_endpoint"] == "https://shared.example/api/projects/p"
