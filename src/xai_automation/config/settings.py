from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from xai_automation.config.env_loader import env, load_dotenv_best_effort


def _as_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    v = value.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _as_csv(value: str | None) -> list[str]:
    if value is None or value.strip() == "":
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str

    nvidia_api_key: str
    nvidia_api_base_url: str
    deepseek_model: str

    x_bearer_token: str
    x_api_key: str
    x_api_secret: str
    x_sources: str
    x_accounts: list[str]
    x_list_id: str
    x_include_keywords: list[str]
    x_exclude_keywords: list[str]
    x_language_hint: list[str]

    higgsfield_mcp_url: str
    higgsfield_api_key: str
    higgsfield_timeout_seconds: int

    tiktok_access_token: str
    tiktok_refresh_token: str
    tiktok_client_key: str
    tiktok_client_secret: str

    meta_access_token: str
    meta_app_id: str
    meta_app_secret: str
    instagram_business_account_id: str
    facebook_page_id: str

    data_dir: Path
    sqlite_path: Path
    output_dir: Path
    assets_dir: Path
    log_level: str

    poll_interval_minutes: int
    max_posts_per_tick: int
    max_concurrency: int
    require_approval: bool

    timeout_seconds_x: int
    timeout_seconds_deepseek: int
    timeout_seconds_publish: int

    retry_max: int
    retry_backoff_seconds: int

    max_post_chars: int
    max_model_output_tokens: int

    higgsfield_tool_name: str
    public_base_url: str
    asset_server_port: int

    meta_graph_api_version: str
    tiktok_api_base_url: str

    def to_public_dict(self) -> dict[str, str]:
        return {
            "APP_NAME": self.app_name,
            "ENVIRONMENT": self.environment,
            "DEEPSEEK_MODEL": self.deepseek_model,
            "X_SOURCES": self.x_sources,
            "X_ACCOUNTS": ",".join(self.x_accounts),
            "X_LIST_ID": self.x_list_id,
            "POLL_INTERVAL_MINUTES": str(self.poll_interval_minutes),
            "MAX_POSTS_PER_TICK": str(self.max_posts_per_tick),
            "MAX_CONCURRENCY": str(self.max_concurrency),
            "REQUIRE_APPROVAL": str(self.require_approval).lower(),
            "SQLITE_PATH": str(self.sqlite_path),
            "OUTPUT_DIR": str(self.output_dir),
            "ASSETS_DIR": str(self.assets_dir),
            "ASSET_SERVER_PORT": str(self.asset_server_port),
            "LOG_LEVEL": self.log_level,
        }


def load_settings() -> Settings:
    load_dotenv_best_effort()

    data_dir = Path(env("DATA_DIR", "./data") or "./data")
    sqlite_path = Path(env("SQLITE_PATH", str(data_dir / "app.db")) or str(data_dir / "app.db"))
    output_dir = Path(env("OUTPUT_DIR", "./out") or "./out")
    assets_dir = Path(env("ASSETS_DIR", str(output_dir / "assets")) or str(output_dir / "assets"))

    return Settings(
        app_name=env("APP_NAME", "x_ai_content_automation") or "x_ai_content_automation",
        environment=env("ENVIRONMENT", "local") or "local",
        nvidia_api_key=env("NVIDIA_API_KEY", "") or "",
        nvidia_api_base_url=env("NVIDIA_API_BASE_URL", "") or "",
        deepseek_model=env("DEEPSEEK_MODEL", "deepseek-v4-prod") or "deepseek-v4-prod",
        x_bearer_token=env("X_BEARER_TOKEN", "") or "",
        x_api_key=env("X_API_KEY", "") or "",
        x_api_secret=env("X_API_SECRET", "") or "",
        x_sources=env("X_SOURCES", "timeline") or "timeline",
        x_accounts=_as_csv(env("X_ACCOUNTS", "")),
        x_list_id=env("X_LIST_ID", "") or "",
        x_include_keywords=_as_csv(
            env(
                "X_INCLUDE_KEYWORDS",
                "ai,artificial intelligence,openai,anthropic,deepseek,llm,genai,model,benchmark,agent,rag,vision,multimodal",
            )
        ),
        x_exclude_keywords=_as_csv(env("X_EXCLUDE_KEYWORDS", "giveaway,airdrop,crypto,nft,casino,betting,adult")),
        x_language_hint=_as_csv(env("X_LANGUAGE_HINT", "en,es")),
        higgsfield_mcp_url=env("HIGGSFIELD_MCP_URL", "") or "",
        higgsfield_api_key=env("HIGGSFIELD_API_KEY", "") or "",
        higgsfield_timeout_seconds=_as_int(env("HIGGSFIELD_TIMEOUT_SECONDS", "900"), 900),
        tiktok_access_token=env("TIKTOK_ACCESS_TOKEN", "") or "",
        tiktok_refresh_token=env("TIKTOK_REFRESH_TOKEN", "") or "",
        tiktok_client_key=env("TIKTOK_CLIENT_KEY", "") or "",
        tiktok_client_secret=env("TIKTOK_CLIENT_SECRET", "") or "",
        meta_access_token=env("META_ACCESS_TOKEN", "") or "",
        meta_app_id=env("META_APP_ID", "") or "",
        meta_app_secret=env("META_APP_SECRET", "") or "",
        instagram_business_account_id=env("INSTAGRAM_BUSINESS_ACCOUNT_ID", "") or "",
        facebook_page_id=env("FACEBOOK_PAGE_ID", "") or "",
        data_dir=data_dir,
        sqlite_path=sqlite_path,
        output_dir=output_dir,
        assets_dir=assets_dir,
        log_level=env("LOG_LEVEL", "INFO") or "INFO",
        poll_interval_minutes=_as_int(env("POLL_INTERVAL_MINUTES", "15"), 15),
        max_posts_per_tick=_as_int(env("MAX_POSTS_PER_TICK", "10"), 10),
        max_concurrency=_as_int(env("MAX_CONCURRENCY", "1"), 1),
        require_approval=_as_bool(env("REQUIRE_APPROVAL", "true"), True),
        timeout_seconds_x=_as_int(env("TIMEOUT_SECONDS_X", "20"), 20),
        timeout_seconds_deepseek=_as_int(env("TIMEOUT_SECONDS_DEEPSEEK", "35"), 35),
        timeout_seconds_publish=_as_int(env("TIMEOUT_SECONDS_PUBLISH", "60"), 60),
        retry_max=_as_int(env("RETRY_MAX", "3"), 3),
        retry_backoff_seconds=_as_int(env("RETRY_BACKOFF_SECONDS", "5"), 5),
        max_post_chars=_as_int(env("MAX_POST_CHARS", "800"), 800),
        max_model_output_tokens=_as_int(env("MAX_MODEL_OUTPUT_TOKENS", "700"), 700),
        higgsfield_tool_name=env("HIGGSFIELD_TOOL_NAME", "") or "",
        public_base_url=env("PUBLIC_BASE_URL", "") or "",
        asset_server_port=_as_int(env("ASSET_SERVER_PORT", "8088"), 8088),
        meta_graph_api_version=env("META_GRAPH_API_VERSION", "v19.0") or "v19.0",
        tiktok_api_base_url=env("TIKTOK_API_BASE_URL", "https://open.tiktokapis.com") or "https://open.tiktokapis.com",
    )
