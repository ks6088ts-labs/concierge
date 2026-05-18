import logging

from concierge.settings import get_project_settings


def enable_verbose_logging() -> None:
    """Switch root and all already-created ``concierge.*`` loggers to DEBUG.

    ``get_logger`` creates each ``concierge.*`` logger with its own level
    and handler at import time, so ``logging.basicConfig(level=DEBUG)``
    alone never raises their effective level. This helper walks the
    ``logging`` manager and bumps both the logger level and the level of
    every attached handler to DEBUG so ``--verbose`` actually surfaces
    DEBUG records emitted by ``concierge.*`` modules. The root logger is
    also configured so DEBUG records from third-party libraries (e.g.
    ``asyncio``) appear too. Idempotent.
    """
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.DEBUG)
    else:
        root.setLevel(logging.DEBUG)
    for name in list(logging.Logger.manager.loggerDict):
        if name == "concierge" or name.startswith("concierge."):
            logger = logging.getLogger(name)
            logger.setLevel(logging.DEBUG)
            for handler in logger.handlers:
                handler.setLevel(logging.DEBUG)


def get_logger(
    name: str = "default",
    log_level: str | None = None,
) -> logging.Logger:
    """
    Get a logger with the specified name.

    If the logger already has handlers, it is returned as-is to avoid
    adding duplicate handlers on repeated calls.

    Args:
        name (str): The name of the logger.
        log_level (str | None): The logging level. Defaults to the project setting.
    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    if log_level is None:
        log_level = get_project_settings().project_log_level

    logger.setLevel(log_level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
