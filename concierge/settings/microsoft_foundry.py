from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MicrosoftFoundrySettings(BaseSettings):
    azure_ai_project_endpoint: str = ""
    azure_ai_project_endpoint_realtime: str = ""
    azure_ai_project_endpoint_image: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_microsoft_foundry_settings() -> MicrosoftFoundrySettings:
    return MicrosoftFoundrySettings()
