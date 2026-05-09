import logging

import pytest

from template_python.core import hello_world
from template_python.loggers import get_logger

logger = get_logger(__name__)


@pytest.fixture(scope="session")
def setup_session():
    """
    Session-wide setup fixture that initializes resources
    needed for the tests. This fixture runs once per test session.
    It can be used to set up resources that are shared across multiple tests.
    """
    logger.info("[SETUP] Starting session-wide setup")
    resource = {"key": "value"}
    yield resource
    logger.info("[TEARDOWN] Cleaning up session-wide resources")


def test_hello_world_verbose(caplog):
    """
    Test the hello_world function with verbose output.
    This test checks if the function logs the expected message.
    """
    logger.info("[TEST] Running test_hello_world_verbose")
    with caplog.at_level(logging.DEBUG, logger="template_python.core"):
        hello_world(verbose=True)
    assert "Hello World" in caplog.text


def test_hello_world_non_verbose(caplog):
    """
    Test the hello_world function without verbose output.
    This test checks that the DEBUG-level message does not appear
    when verbose is False.
    """
    logger.info("[TEST] Running test_hello_world_non_verbose")
    with caplog.at_level(logging.INFO):
        hello_world(verbose=False)
    assert "Hello World" in caplog.text  # now logged at INFO level


@pytest.mark.parametrize(
    "verbose, log_level",
    [
        (True, logging.DEBUG),
        (False, logging.INFO),
    ],
)
def test_hello_world_parametrized(caplog, verbose, log_level):
    """
    Parametrized test for the hello_world function.
    Regardless of verbosity the message 'Hello World' should appear
    when capturing at the appropriate level.
    """
    logger.info(f"[TEST] Running test_hello_world_parametrized with verbose={verbose}")
    with caplog.at_level(log_level, logger="template_python.core"):
        hello_world(verbose=verbose)
    assert "Hello World" in caplog.text
