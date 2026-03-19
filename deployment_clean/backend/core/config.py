"""
v7 configuration via pydantic-settings and .env.
Paths, AMAIZ, MCP, Keycloak placeholders. No code copied from v3/v4.
"""

from __future__ import annotations

import functools
from pathlib import Path

from pydantic_settings import BaseSettings


def _find_env_file() -> str:
    here = Path(__file__).resolve().parent
    for ancestor in [here.parent.parent, here.parent.parent.parent]:
        candidate = ancestor / ".env"
        if candidate.exists():
            return str(candidate)
    return ".env"


class Settings(BaseSettings):
    app_host: str = "127.0.0.1"
    app_port: int = 8004

    # AMAIZ
    AMAIZ_TENANT_ID: str = ""
    AMAIZ_BASE_URL: str = ""
    AMAIZ_API_KEY: str = ""
    AMAIZ_GENAIAPP_RUNTIME_ID: str = ""
    HTTPX_REQUEST_TIMEOUT: int = 600
    AMAIZ_CHAT_FLOW_NAME: str = "chat"
    AMAIZ_FLOW_NAME: str = "db_analysis_amaiz_pipeline"
    AMAIZ_CONTEXT_KEY: str = "context_data"
    # When True, use the chat flow for all pipeline agent calls (workaround when pipeline flow returns "last step" error).
    USE_CHAT_FLOW_FOR_PIPELINE: bool = False

    # Paths (v7 root)
    prompts_dir: str = "prompts"
    reports_dir: str = "reports"
    data_dir: str = "data"
    memory_dir: str = "memory"

    # DB
    db_connections_file: str = "db_connections.yaml"
    db_connect_timeout: int = 30
    postgres_dsn: str = ""
    couchbase_connection_string: str = "couchbase://localhost"
    couchbase_bucket: str = ""
    couchbase_username: str = ""
    couchbase_password: str = ""

    # MCP defaults
    mcp_postgres_dsn: str = ""
    mcp_couchbase_connection_string: str = ""
    mcp_couchbase_bucket: str = ""
    mcp_couchbase_username: str = ""
    mcp_couchbase_password: str = ""

    # Keycloak (optional — if server_url is empty, system runs in dev/API-key mode)
    keycloak_server_url: str = ""
    keycloak_realm: str = ""
    keycloak_client_id: str = ""
    keycloak_client_secret: str = ""

    # Security
    api_key: str = ""
    cors_allowed_origins: str = "*"
    # Comma-separated extra CORS origins (e.g. "https://tracewise-ui:8443"). Set per environment.
    cors_extra_origins: str = ""
    body_size_limit_mib: int = 50

    # Schema cache
    schema_cache_ttl_seconds: int = 300

    # Monitoring
    monitoring_interval_minutes: int = 10

    # LLM context
    llm_max_context_tokens: int = 16000

    # Pipeline
    pipeline_stage_timeout: int = 90
    pipeline_max_concurrency: int = 5

    # Circuit breaker (AMAIZ)
    circuit_breaker_failures: int = 10
    circuit_breaker_seconds: int = 60

    # Logging
    log_level: str = "INFO"
    environment: str = "dev"

    @property
    def amaiz_configured(self) -> bool:
        return bool(
            self.AMAIZ_BASE_URL
            and self.AMAIZ_API_KEY
            and self.AMAIZ_TENANT_ID
            and self.AMAIZ_GENAIAPP_RUNTIME_ID
        )

    model_config = {"env_file": _find_env_file(), "env_file_encoding": "utf-8", "extra": "ignore"}


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
