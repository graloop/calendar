# The app's settings, read from the environment or from .env (the project root's
# when run from backend/, as `npm start` does).

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # The database lives here: /data in the container, backend/data on the laptop.
    data_dir: str = "./data"

    # Swagger UI at /docs. Off by default so the API isn't advertised.
    enable_api_docs: bool = False

    # Claude's connector (app/mcp/). Off unless turned on in the stack.
    mcp_enabled: bool = False
    # The public hostname that reaches /mcp, e.g. agenda-mcp.graloop.com. On it,
    # the app answers only the connector's paths (app/mcp/guard.py).
    mcp_host: str = ""
    # The connector password's scrypt hash, made by `python -m app.mcp.hashpw`.
    # Never the password itself. Changing it signs Claude out.
    mcp_password_hash: str = ""
    # How long Claude stays connected without the password (refresh token). Access tokens last 1 h.
    mcp_token_days: int = 30

    @field_validator("mcp_host")
    @classmethod
    def _bare_hostname(cls, value: str) -> str:
        """Forgiving about form: "https://Agenda-MCP.graloop.com/" becomes
        "agenda-mcp.graloop.com", the way it's compared with a request's Host."""
        value = value.strip().lower().removeprefix("https://").removeprefix("http://")
        return value.split("/")[0].split(":")[0]

    def mcp_problem(self) -> str | None:
        """Why the connector can't be turned on, or None when it can (or is off)."""
        if not self.mcp_enabled:
            return None
        missing = [name for name in ("MCP_HOST", "MCP_PASSWORD_HASH") if not getattr(self, name.lower())]
        if missing:
            return f"MCP_ENABLED is true but {' and '.join(missing)} is empty: the connector stays off."
        if not self.mcp_password_hash.startswith("scrypt$"):
            return "MCP_PASSWORD_HASH isn't a hash from `python -m app.mcp.hashpw`: the connector stays off."
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
