"""Connection settings for Azure Database for PostgreSQL (Flexible Server).

The variable names follow the
[Microsoft Learn LangChain tutorial](https://learn.microsoft.com/en-us/azure/postgresql/azure-ai/generative-ai-develop-with-langchain),
but are prefixed with ``AZURE_`` here so they cannot be confused with the
local pgvector ``POSTGRES_*`` variables. Expected variables:

``AZURE_DBHOST``, ``AZURE_DBNAME``, ``AZURE_DBUSER``, ``AZURE_DBPASSWORD``,
``AZURE_DBPORT``, ``AZURE_SSLMODE``, ``AZURE_USE_ENTRA_AUTH``, and (optional)
``AZURE_ENTRA_TOKEN_SCOPE``. When ``AZURE_USE_ENTRA_AUTH=true`` the
unified CRUD CLI in ``scripts/postgresql/vanilla.py`` (run with
``--target azure``) fetches an access token via ``DefaultAzureCredential``
and uses it as the database password.
"""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class AzurePostgresSettings(BaseSettings):
    """Azure Database for PostgreSQL connection settings."""

    dbhost: str = ""
    dbname: str = ""
    dbuser: str = ""
    dbpassword: str = ""
    dbport: int = 5432
    sslmode: str = "require"
    # When true, ``scripts/postgresql/vanilla.py --target azure`` ignores
    # ``AZURE_DBUSER``/``AZURE_DBPASSWORD`` for the password and instead
    # fetches an Entra access token via ``DefaultAzureCredential``. The
    # Entra principal used must already be a PostgreSQL role configured for
    # Microsoft Entra authentication.
    use_entra_auth: bool = True
    # Override only if your tenant requires a non-default audience.
    entra_token_scope: str = "https://ossrdbms-aad.database.windows.net/.default"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="AZURE_",
        extra="ignore",
    )

    def build_connection_string(self, *, password: str, user: str | None = None) -> str:
        """Return a SQLAlchemy ``postgresql+psycopg://...`` URL for Azure.

        Both the username and the password (which may be an Entra access
        token containing URL-unsafe characters) are URL-escaped.
        """
        effective_user = user or self.dbuser
        escaped_user = quote_plus(effective_user)
        escaped_password = quote_plus(password)
        return (
            f"postgresql+psycopg://{escaped_user}:{escaped_password}"
            f"@{self.dbhost}:{self.dbport}/{self.dbname}?sslmode={self.sslmode}"
        )


@lru_cache
def get_azure_postgres_settings() -> AzurePostgresSettings:
    return AzurePostgresSettings()
