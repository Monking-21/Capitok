import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Capitok Archive Gateway"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql://postgres:postgres@localhost:5432/capitok"

    # JSON format: {"dev-key": {"tenant_id": "demo", "principal_id": "operator", "scopes": ["ingest","search"]}}
    auth_api_keys_json: str = "{}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def api_key_map(self) -> dict:
        try:
            parsed = json.loads(self.auth_api_keys_json)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
