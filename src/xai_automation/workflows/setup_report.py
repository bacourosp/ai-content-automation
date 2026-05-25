from __future__ import annotations

from xai_automation.config.settings import Settings
from xai_automation.services.callback_urls import compute_callback_urls, normalize_base_url


def _yn(value: str) -> str:
    return "OK" if (value or "").strip() else "FALTA"


def _render_provider_lines(settings) -> list[str]:
    p = settings.render_provider
    out = [
        "--- Render de video (RENDER_PROVIDER) ---",
        f"RENDER_PROVIDER   = {p}",
        "Opciones: higgsfield | mcp (HTTP genérico) | glif | remotion_media | remotion_app",
    ]
    if p == "higgsfield":
        out.append(f"  higgsfield: HIGGSFIELD_MCP_URL={_yn(settings.higgsfield_mcp_url)}  HIGGSFIELD_API_KEY={_yn(settings.higgsfield_api_key)}")
    elif p == "glif":
        out.append(f"  glif: GLIF_API_TOKEN={_yn(settings.glif_api_token)}  GLIF_RENDER_ID={_yn(settings.glif_render_id)}  (oficial; restringido a un glif id fijo)")
        out.append(f"        cmd={settings.glif_mcp_command}")
    elif p == "remotion_media":
        out.append(f"  remotion_media: KIE_API_KEY={_yn(settings.kie_api_key)}  (terceros vía kie.ai)")
        out.append(f"        cmd={settings.remotion_media_mcp_command}")
    elif p == "remotion_app":
        out.append(f"  remotion_app: REMOTION_APP_MCP_URL={_yn(settings.remotion_app_mcp_url)}")
        out.append("        AVISO: ejecuta código generado por IA (ACE). SOLO self-host (URL local/privada).")
    else:
        out.append(f"  mcp (genérico HTTP): RENDER_MCP_URL={_yn(settings.render_mcp_url)}  RENDER_TOOL_NAME={settings.render_tool_name or '(auto)'}")
    out.append(f"  Imágenes (Gemini oficial): ENABLE_IMAGE_GEN={str(settings.enable_image_gen).lower()}  modelo={settings.gemini_image_model}")
    return out


def build_setup_report(*, settings: Settings, public_base_url: str) -> str:
    base = normalize_base_url(public_base_url)
    urls = compute_callback_urls(base) if base else {}
    lines: list[str] = []

    lines.append("================ SETUP / CALLBACKS ================")
    lines.append(f"LLM_PROVIDER      = {settings.llm_provider}")
    if settings.llm_provider == "gemini":
        lines.append(f"GEMINI_MODEL      = {settings.gemini_model}  (API key: {_yn(settings.gemini_api_key)})")
    else:
        lines.append(f"DEEPSEEK_MODEL    = {settings.deepseek_model}  (NVIDIA key: {_yn(settings.nvidia_api_key)})")
    lines.append(f"X_BEARER_TOKEN    = {_yn(settings.x_bearer_token)}")
    lines.append("")
    lines.extend(_render_provider_lines(settings))
    lines.append("")

    if not base:
        lines.append("PUBLIC_BASE_URL no está definida todavía.")
        lines.append("Levanta el tunnel con:  xai-automation serve-assets   (escribe PUBLIC_BASE_URL en .env)")
        lines.append("===================================================")
        return "\n".join(lines)

    lines.append(f"PUBLIC_BASE_URL   = {base}")
    lines.append("")
    lines.append("--- Redirect URIs (pégalos en los dashboards) ---")
    lines.append(f"TikTok redirect URI : {urls['TIKTOK_REDIRECT_URI']}")
    lines.append(f"Meta  redirect URI  : {urls['META_REDIRECT_URI']}")
    lines.append("")
    lines.append("--- Conectar cuentas (abre en el navegador) ---")
    lines.append(f"TikTok : {base}/oauth/tiktok/start")
    lines.append(f"Meta   : {base}/oauth/meta/start")
    lines.append("(al terminar, los tokens se guardan automáticamente en .env)")
    lines.append("")
    lines.append("--- Hosting de video (Instagram lo descarga de aquí) ---")
    lines.append(f"{urls['ASSETS_VIDEO_URL_TEMPLATE']}")
    lines.append("")
    lines.append("--- Checklist por plataforma ---")
    lines.append("TikTok (developers.tiktok.com): app con Content Posting API; scopes video.publish,video.upload;")
    lines.append("        registra la redirect URI de arriba. Client key/secret -> TIKTOK_CLIENT_KEY/SECRET.")
    lines.append("Meta (developers.facebook.com): app Business; productos Facebook Login + Instagram Graph;")
    lines.append("        scopes instagram_content_publish, pages_manage_posts, pages_read_engagement; redirect URI de arriba.")
    lines.append("        App ID/Secret -> META_APP_ID/META_APP_SECRET. IG debe ser cuenta Business ligada a una Página.")
    lines.append("X (developer.x.com): Bearer token v2 -> X_BEARER_TOKEN.")
    lines.append("Higgsfield: MCP URL + API key -> HIGGSFIELD_MCP_URL/HIGGSFIELD_API_KEY (opcional HIGGSFIELD_TOOL_NAME).")
    if settings.enable_cloudflare_tunnel and not settings.cloudflare_tunnel_token.strip():
        lines.append("")
        lines.append("NOTA: tunnel efímero -> la URL cambia en cada reinicio; re-registra las redirect URIs si reinicias.")
    lines.append("===================================================")
    return "\n".join(lines)
