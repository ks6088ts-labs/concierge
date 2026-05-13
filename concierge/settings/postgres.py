from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    """Connection settings for the local pgvector PostgreSQL service.

    Defaults match the ``postgres`` service defined in ``compose.yml`` so
    ``docker compose up postgres`` works without any extra configuration.
    """

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "concierge"
    postgres_password: str = "concierge"
    postgres_db: str = "concierge"
    # Default collection name used by ``langchain_postgres.PGVector``.
    postgres_collection: str = "concierge_docs"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def connection_string(self) -> str:
        """Return the ``postgresql+psycopg://...`` URL expected by ``PGVector``."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_postgres_settings() -> PostgresSettings:
    return PostgresSettings()
