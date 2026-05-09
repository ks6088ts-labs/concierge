from logging import DEBUG

from dotenv import load_dotenv

from concierge.loggers import get_logger
from concierge.settings import Settings

logger = get_logger(__name__)


def test_settings(caplog):
    """
    Test that Settings loads values correctly from the .env.template file.
    """
    logger.info("[TEST] Running test_settings")
    with caplog.at_level(DEBUG):
        assert load_dotenv(
            dotenv_path=".env.template",
            verbose=True,
        ), "Failed to load environment variables from .env.template"
        settings = Settings()
        assert settings.project_name == "concierge", "Default project name should be 'concierge'"
        logger.debug(f"Settings initialized: {settings}")
