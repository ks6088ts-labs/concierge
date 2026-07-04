class ImageGenerationError(RuntimeError):
    """Raised when image generation via Foundry fails."""


class FileToolError(RuntimeError):
    """Raised when sandboxed file tool operations fail safely."""


class ShellToolError(RuntimeError):
    """Raised when sandboxed shell command execution fails safely."""


class WebFetchError(RuntimeError):
    """Raised when a web page fetch is rejected or fails safely."""
