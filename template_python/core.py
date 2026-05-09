import logging

from template_python.loggers import get_logger

logger = get_logger(__name__)


def hello_world(verbose: bool = False):
    """Log a greeting message.

    Args:
        verbose: If True, the message is logged at DEBUG level.
                 Otherwise it is logged at INFO level.
    """
    if verbose:
        logger.log(logging.DEBUG, "Hello World")
    else:
        logger.log(logging.INFO, "Hello World")


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    hello_world(verbose=True)
