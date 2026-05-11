from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class TodoSettings(BaseSettings):
    app_name: str = "concierge-todo"
    log_level: str = "INFO"
    enable_mlflow: bool = False

    model_config = SettingsConfigDict(
        env_prefix="TODO_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_todo_settings() -> TodoSettings:
    return TodoSettings()
