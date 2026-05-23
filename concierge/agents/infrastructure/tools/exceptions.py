class ImageGenerationError(RuntimeError):
    """Raised when image generation via Foundry fails."""


class FileToolError(RuntimeError):
    """Raised when sandboxed file tool operations fail safely."""


class ShellToolError(RuntimeError):
    """Raised when sandboxed shell command execution fails safely."""
