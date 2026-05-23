"""Image generation tool builder factories.

The pure ``generate_image()`` function lives in :mod:`.image_generation` and
has no framework dependencies. This module wraps it as a LangChain /
Microsoft Agent Framework / GitHub Copilot SDK tool so unified agent classes
(``LangGraphAgent`` / ``MicrosoftAgentFrameworkAgent`` / ``GitHubCopilotSdkAgent``)
can compose it together with other tools.

Each factory returns a *builder* callable. The agent invokes the builder
once per ``handle()`` with a fresh ``side_outputs`` dict, and the builder
writes the list of generated images back into that dict so the agent can
surface them in ``AgentResponse.result["images"]``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from concierge.agents.infrastructure.tools.image_generation import generate_image


class _GenerateImageParams(BaseModel):
    """Parameter schema for the Copilot SDK image-generation tool.

    Declared at module level because ``copilot.define_tool`` resolves the
    handler's parameter type via :func:`typing.get_type_hints`, which cannot
    see locally-defined classes under ``from __future__ import annotations``.
    """

    prompt: str = Field(description="Prompt describing the image to generate")
    size: str = Field(default="1024x1024", description="Image size, e.g. 1024x1024")
    n: int = Field(default=1, description="Number of images to generate (1-10)")


def image_gen_langchain_tool_factory(save_dir: str) -> Callable[[dict[str, Any]], Any]:
    """Return a builder that produces a LangChain image-generation tool."""

    def _build(side_outputs: dict[str, Any]) -> Any:
        from langchain_core.tools import tool

        generated_images: list[dict[str, Any]] = []
        side_outputs["images"] = generated_images

        @tool
        async def generate_image_tool(prompt: str, size: str = "1024x1024", n: int = 1) -> dict[str, Any]:
            """Generate images with Foundry gpt-image-2 and return metadata."""
            generated = await generate_image(prompt, size=size, n=n, save_dir=save_dir)
            full_images = [
                {
                    "b64_json": image.b64_json,
                    "path": image.path,
                    "revised_prompt": image.revised_prompt,
                }
                for image in generated.images
            ]
            generated_images.extend(full_images)
            return {
                "images": [{"path": image["path"], "revised_prompt": image["revised_prompt"]} for image in full_images],
                "size": generated.size,
                "model": generated.model,
            }

        return generate_image_tool

    return _build


def image_gen_maf_tool_factory(save_dir: str) -> Callable[[dict[str, Any]], Any]:
    """Return a builder that produces a Microsoft Agent Framework image-generation tool."""

    def _build(side_outputs: dict[str, Any]) -> Any:
        from agent_framework import tool

        generated_images: list[dict[str, Any]] = []
        side_outputs["images"] = generated_images

        @tool
        async def generate_image_tool(prompt: str, size: str = "1024x1024", n: int = 1) -> dict[str, Any]:
            """Generate images with Foundry gpt-image-2 and return metadata."""
            generated = await generate_image(prompt, size=size, n=n, save_dir=save_dir)
            full_images = [
                {
                    "b64_json": image.b64_json,
                    "path": image.path,
                    "revised_prompt": image.revised_prompt,
                }
                for image in generated.images
            ]
            generated_images.extend(full_images)
            return {
                "images": [{"path": image["path"], "revised_prompt": image["revised_prompt"]} for image in full_images],
                "size": generated.size,
                "model": generated.model,
            }

        return generate_image_tool

    return _build


def image_gen_copilot_sdk_tool_factory(save_dir: str) -> Callable[[dict[str, Any]], Any]:
    """Return a builder that produces a GitHub Copilot SDK image-generation tool."""

    def _build(side_outputs: dict[str, Any]) -> Any:
        from copilot import define_tool

        generated_images: list[dict[str, Any]] = []
        side_outputs["images"] = generated_images

        @define_tool(
            name="generate_image_tool",
            description="Generate images with Foundry gpt-image-2 and return metadata.",
            skip_permission=True,
        )
        async def generate_image_tool(params: _GenerateImageParams) -> dict[str, Any]:
            generated = await generate_image(params.prompt, size=params.size, n=params.n, save_dir=save_dir)
            full_images = [
                {
                    "b64_json": image.b64_json,
                    "path": image.path,
                    "revised_prompt": image.revised_prompt,
                }
                for image in generated.images
            ]
            generated_images.extend(full_images)
            return {
                "images": [{"path": image["path"], "revised_prompt": image["revised_prompt"]} for image in full_images],
                "size": generated.size,
                "model": generated.model,
            }

        return generate_image_tool

    return _build
