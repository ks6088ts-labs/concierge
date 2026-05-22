from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from concierge.agents.infrastructure.tools.exceptions import ImageGenerationError
from concierge.loggers import get_logger
from concierge.settings import get_agents_settings
from concierge.settings.microsoft_foundry import get_microsoft_foundry_settings

logger = get_logger(__name__)

_VALID_SIZES = {"1024x1024", "1536x1024", "1024x1536", "4K"}


@dataclass(frozen=True)
class GeneratedImage:
    b64_json: str | None
    path: str | None
    revised_prompt: str | None


@dataclass(frozen=True)
class ImageGenerationResult:
    images: list[GeneratedImage]
    model: str
    size: str


def _build_default_client() -> AzureOpenAI:
    settings = get_agents_settings()
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=get_microsoft_foundry_settings().azure_ai_project_endpoint,
        api_version=settings.image_api_version,
        azure_ad_token_provider=token_provider,
    )


def _ensure_valid_size(size: str) -> None:
    if size not in _VALID_SIZES:
        raise ValueError(f"size must be one of {sorted(_VALID_SIZES)}, got: {size}")


def _ensure_valid_n(n: int) -> None:
    if not (1 <= n <= 10):
        raise ValueError(f"n must be between 1 and 10, got: {n}")


def _write_png(save_dir: str, b64_json: str) -> str:
    resolved_dir = Path(save_dir).resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    output_path = (resolved_dir / f"{uuid4().hex}.png").resolve()
    if not output_path.is_relative_to(resolved_dir):
        raise ImageGenerationError("resolved output path escapes save_dir")
    output_path.write_bytes(base64.b64decode(b64_json))
    return str(output_path)


async def generate_image(
    prompt: str,
    *,
    size: str = "1024x1024",
    n: int = 1,
    save_dir: str | None = None,
    client: AzureOpenAI | None = None,
    model: str | None = None,
) -> ImageGenerationResult:
    _ensure_valid_size(size)
    _ensure_valid_n(n)

    settings = get_agents_settings()
    resolved_model = model or settings.image_model
    resolved_client = client or _build_default_client()
    started_at = perf_counter()

    try:
        response = await asyncio.to_thread(
            resolved_client.images.generate,
            model=resolved_model,
            prompt=prompt,
            size=size,
            n=n,
            response_format="b64_json",
        )
    except Exception as exc:  # noqa: BLE001
        raise ImageGenerationError(f"{type(exc).__name__}: failed to generate image") from exc

    images: list[GeneratedImage] = []
    try:
        for item in list(getattr(response, "data", []) or []):
            raw_b64_json = getattr(item, "b64_json", None)
            b64_json = raw_b64_json if isinstance(raw_b64_json, str) else None
            path: str | None = None
            if save_dir and b64_json:
                path = await asyncio.to_thread(_write_png, save_dir, b64_json)
            raw_revised_prompt = getattr(item, "revised_prompt", None)
            revised_prompt = raw_revised_prompt if isinstance(raw_revised_prompt, str) else None
            images.append(
                GeneratedImage(
                    b64_json=b64_json,
                    path=path,
                    revised_prompt=revised_prompt,
                )
            )
    except Exception as exc:  # noqa: BLE001
        raise ImageGenerationError(f"{type(exc).__name__}: failed to process generated image") from exc

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    logger.info("%s images generated in %sms (size=%s, model=%s)", len(images), elapsed_ms, size, resolved_model)
    for image in images:
        if image.revised_prompt:
            logger.debug("image revised_prompt=%s", image.revised_prompt)

    return ImageGenerationResult(images=images, model=resolved_model, size=size)
