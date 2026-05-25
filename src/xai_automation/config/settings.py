from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from xai_automation.config.env_loader import env, load_dotenv_best_effort


def _as_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _as_float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


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
    llm_provider: str
    gemini_api_key: str
    gemini_model: str
    gemini_thinking_budget: int

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
    higgsfield_api_key_id: str
    higgsfield_api_key_secret: str
    higgsfield_timeout_seconds: int
    higgsfield_arg_name: str
    higgsfield_cost_per_video_usd: float
    higgsfield_free_tier_monthly_usd: float
    higgsfield_free_tier_monthly_videos: int

    # Render provider selection + alternative content-generation MCP providers.
    render_provider: str
    render_mcp_url: str
    render_api_key: str
    render_tool_name: str
    render_arg_name: str
    render_input_kind: str
    render_cost_per_video_usd: float
    render_free_tier_monthly_usd: float
    render_free_tier_monthly_videos: int
    glif_api_token: str
    glif_render_id: str
    glif_tool_name: str
    glif_mcp_command: str
    kie_api_key: str
    remotion_media_mcp_command: str
    remotion_app_mcp_url: str
    enable_image_gen: bool
    gemini_image_model: str

    tiktok_access_token: str
    tiktok_refresh_token: str
    tiktok_client_key: str
    tiktok_client_secret: str
    tiktok_scopes: str

    meta_access_token: str
    meta_app_id: str
    meta_app_secret: str
    instagram_business_account_id: str
    facebook_page_id: str
    meta_scopes: str

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
    webhook_port: int
    enable_cloudflare_tunnel: bool
    cloudflare_tunnel_token: str

    meta_graph_api_version: str
    tiktok_api_base_url: str

    def to_public_dict(self) -> dict[str, str]:
        return {
            "APP_NAME": self.app_name,
            "ENVIRONMENT": self.environment,
            "DEEPSEEK_MODEL": self.deepseek_model,
            "LLM_PROVIDER": self.llm_provider,
            "GEMINI_MODEL": self.gemini_model,
            "RENDER_PROVIDER": self.render_provider,
            "ENABLE_IMAGE_GEN": str(self.enable_image_gen).lower(),
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
            "WEBHOOK_PORT": str(self.webhook_port),
            "ENABLE_CLOUDFLARE_TUNNEL": str(self.enable_cloudflare_tunnel).lower(),
            "LOG_LEVEL": self.log_level,
            "HIGGSFIELD_COST_PER_VIDEO_USD": str(self.higgsfield_cost_per_video_usd),
            "HIGGSFIELD_FREE_TIER_MONTHLY_USD": str(self.higgsfield_free_tier_monthly_usd),
            "HIGGSFIELD_FREE_TIER_MONTHLY_VIDEOS": str(self.higgsfield_free_tier_monthly_videos),
        }


def load_settings() -> Settings:
    load_dotenv_best_effort()

    data_dir = Path(env("DATA_DIR", "./data") or "./data")
    sqlite_path = Path(env("SQLITE_PATH", str(data_dir / "app.db")) or str(data_dir / "app.db"))
    output_dir = Path(env("OUTPUT_DIR", "./out") or "./out")
    assets_dir = Path(env("ASSETS_DIR", str(output_dir / "assets")) or str(output_dir / "assets"))
    asset_server_port = _as_int(env("ASSET_SERVER_PORT", "8088"), 8088)
    webhook_port = _as_int(env("WEBHOOK_PORT", str(asset_server_port)), asset_server_port)

    return Settings(
        app_name=env("APP_NAME", "x_ai_content_automation") or "x_ai_content_automation",
        environment=env("ENVIRONMENT", "local") or "local",
        nvidia_api_key=env("NVIDIA_API_KEY", "") or "",
        nvidia_api_base_url=env("NVIDIA_API_BASE_URL", "") or "",
        deepseek_model=env("DEEPSEEK_MODEL", "deepseek-ai/deepseek-v3.1-terminus") or "deepseek-ai/deepseek-v3.1-terminus",
        llm_provider=(env("LLM_PROVIDER", "gemini") or "gemini").strip().lower(),
        gemini_api_key=env("GEMINI_API_KEY", "") or "",
        gemini_model=env("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash",
        gemini_thinking_budget=_as_int(env("GEMINI_THINKING_BUDGET", "0"), 0),
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
        higgsfield_api_key=env("HIGGSFIELD_API_KEY", "") or (env("HIGGSFIELD_API_KEY_SECRET", "") or ""),
        higgsfield_api_key_id=env("HIGGSFIELD_API_KEY_ID", "") or "",
        higgsfield_api_key_secret=env("HIGGSFIELD_API_KEY_SECRET", "") or "",
        higgsfield_timeout_seconds=_as_int(env("HIGGSFIELD_TIMEOUT_SECONDS", "900"), 900),
        higgsfield_arg_name=env("HIGGSFIELD_ARG_NAME", "video_spec") or "video_spec",
        higgsfield_cost_per_video_usd=_as_float(env("HIGGSFIELD_COST_PER_VIDEO_USD", "0"), 0.0),
        higgsfield_free_tier_monthly_usd=_as_float(env("HIGGSFIELD_FREE_TIER_MONTHLY_USD", "0"), 0.0),
        higgsfield_free_tier_monthly_videos=_as_int(env("HIGGSFIELD_FREE_TIER_MONTHLY_VIDEOS", "0"), 0),
        render_provider=(env("RENDER_PROVIDER", "higgsfield") or "higgsfield").strip().lower(),
        render_mcp_url=env("RENDER_MCP_URL", "") or "",
        render_api_key=env("RENDER_API_KEY", "") or "",
        render_tool_name=env("RENDER_TOOL_NAME", "") or "",
        render_arg_name=env("RENDER_ARG_NAME", "") or "",
        render_input_kind=(env("RENDER_INPUT_KIND", "spec") or "spec").strip().lower(),
        render_cost_per_video_usd=_as_float(env("RENDER_COST_PER_VIDEO_USD", "0"), 0.0),
        render_free_tier_monthly_usd=_as_float(env("RENDER_FREE_TIER_MONTHLY_USD", "0"), 0.0),
        render_free_tier_monthly_videos=_as_int(env("RENDER_FREE_TIER_MONTHLY_VIDEOS", "0"), 0),
        glif_api_token=env("GLIF_API_TOKEN", "") or "",
        glif_render_id=env("GLIF_RENDER_ID", "") or "",
        glif_tool_name=env("GLIF_TOOL_NAME", "run_glif") or "run_glif",
        glif_mcp_command=env("GLIF_MCP_COMMAND", "npx -y @glifxyz/glif-mcp-server@0.9.9") or "npx -y @glifxyz/glif-mcp-server@0.9.9",
        kie_api_key=env("KIE_API_KEY", "") or "",
        remotion_media_mcp_command=env("REMOTION_MEDIA_MCP_COMMAND", "npx -y remotion-media-mcp@1.2.2") or "npx -y remotion-media-mcp@1.2.2",
        remotion_app_mcp_url=env("REMOTION_APP_MCP_URL", "") or "",
        enable_image_gen=_as_bool(env("ENABLE_IMAGE_GEN", "false"), False),
        gemini_image_model=env("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image") or "gemini-2.5-flash-image",
        tiktok_access_token=env("TIKTOK_ACCESS_TOKEN", "") or "",
        tiktok_refresh_token=env("TIKTOK_REFRESH_TOKEN", "") or "",
        tiktok_client_key=env("TIKTOK_CLIENT_KEY", "") or "",
        tiktok_client_secret=env("TIKTOK_CLIENT_SECRET", "") or "",
        tiktok_scopes=env("TIKTOK_SCOPES", "video.publish,video.upload") or "video.publish,video.upload",
        meta_access_token=env("META_ACCESS_TOKEN", "") or "",
        meta_app_id=env("META_APP_ID", "") or "",
        meta_app_secret=env("META_APP_SECRET", "") or "",
        instagram_business_account_id=env("INSTAGRAM_BUSINESS_ACCOUNT_ID", "") or "",
        facebook_page_id=env("FACEBOOK_PAGE_ID", "") or "",
        meta_scopes=env(
            "META_SCOPES",
            "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,pages_manage_posts,business_management",
        )
        or "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,pages_manage_posts,business_management",
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
        max_model_output_tokens=_as_int(env("MAX_MODEL_OUTPUT_TOKENS", "4000"), 4000),
        higgsfield_tool_name=env("HIGGSFIELD_TOOL_NAME", "") or "",
        public_base_url=env("PUBLIC_BASE_URL", "") or "",
        asset_server_port=asset_server_port,
        webhook_port=webhook_port,
        enable_cloudflare_tunnel=_as_bool(env("ENABLE_CLOUDFLARE_TUNNEL", "false"), False),
        cloudflare_tunnel_token=env("CLOUDFLARE_TUNNEL_TOKEN", "") or "",
        meta_graph_api_version=env("META_GRAPH_API_VERSION", "v19.0") or "v19.0",
        tiktok_api_base_url=env("TIKTOK_API_BASE_URL", "https://open.tiktokapis.com") or "https://open.tiktokapis.com",
    )
