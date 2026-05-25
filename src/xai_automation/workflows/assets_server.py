from __future__ import annotations

import http.server
import logging
import secrets
import socketserver
from html import escape
from typing import Any
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from xai_automation.config.env_writer import default_env_path, set_env_vars
from xai_automation.config.settings import Settings
from xai_automation.connectors.oauth_meta import MetaOAuth, MetaOAuthConfig, meta_authorize_url
from xai_automation.connectors.oauth_tiktok import TikTokOAuth, TikTokOAuthConfig, tiktok_authorize_url

log = logging.getLogger("xai_automation.assets_server")


def _tiktok_callback(settings: Settings, *, code: str, redirect_uri: str) -> dict[str, str]:
    oa = TikTokOAuth(
        TikTokOAuthConfig(
            client_key=settings.tiktok_client_key,
            client_secret=settings.tiktok_client_secret,
            api_base=settings.tiktok_api_base_url,
        )
    )
    tok = oa.exchange_code(code=code, redirect_uri=redirect_uri)
    access = str((tok or {}).get("access_token") or "")
    refresh = str((tok or {}).get("refresh_token") or "")
    if access == "":
        raise RuntimeError(f"tiktok token response missing access_token: {tok}")
    return {"TIKTOK_ACCESS_TOKEN": access, "TIKTOK_REFRESH_TOKEN": refresh}


def _meta_callback(settings: Settings, *, code: str, redirect_uri: str) -> dict[str, str]:
    oa = MetaOAuth(MetaOAuthConfig(app_id=settings.meta_app_id, app_secret=settings.meta_app_secret, api_version=settings.meta_graph_api_version))
    short = oa.exchange_code(code=code, redirect_uri=redirect_uri)
    short_token = str((short or {}).get("access_token") or "")
    if short_token == "":
        raise RuntimeError(f"meta token response missing access_token: {short}")
    longed = oa.exchange_long_lived(short_token=short_token)
    user_token = str((longed or {}).get("access_token") or short_token)

    pages = oa.list_pages(user_token=user_token)
    if not pages:
        # No page yet: still persist the user token so Graph calls can be configured manually.
        return {"META_ACCESS_TOKEN": user_token}
    page = pages[0]
    page_id = str(page.get("id") or "")
    page_token = str(page.get("access_token") or user_token)
    ig_id = oa.get_ig_business_account(page_id=page_id, page_token=page_token)
    out = {"META_ACCESS_TOKEN": page_token, "FACEBOOK_PAGE_ID": page_id}
    if ig_id:
        out["INSTAGRAM_BUSINESS_ACCOUNT_ID"] = ig_id
    return out


def _make_handler(*, settings: Settings, directory: str, public_base_url: str, oauth_state: dict[str, float]):
    base = (public_base_url or "").rstrip("/")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003 - stdlib signature
            log.info("assets " + fmt, *args)

        def _send(self, status: int, body: str, *, content_type: str = "text/html; charset=utf-8") -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self, url: str) -> None:
            self.send_response(302)
            self.send_header("Location", url)
            self.end_headers()

        def _start_oauth(self, provider: str) -> None:
            if base == "":
                self._send(400, "<h1>PUBLIC_BASE_URL no configurada</h1><p>Levanta serve-assets con el tunnel o define PUBLIC_BASE_URL.</p>")
                return
            state = secrets.token_urlsafe(24)
            oauth_state[state] = 0.0
            if provider == "tiktok":
                url = tiktok_authorize_url(
                    client_key=settings.tiktok_client_key,
                    redirect_uri=base + "/callback/tiktok",
                    state=state,
                    scope=settings.tiktok_scopes,
                )
            else:
                url = meta_authorize_url(
                    app_id=settings.meta_app_id,
                    redirect_uri=base + "/callback/meta",
                    state=state,
                    scope=settings.meta_scopes,
                    api_version=settings.meta_graph_api_version,
                )
            self._redirect(url)

        def _handle_callback(self, provider: str, qs: dict[str, list[str]]) -> None:
            err = (qs.get("error") or qs.get("error_description") or [""])[0]
            if err:
                self._send(400, f"<h1>OAuth error</h1><p>{escape(err)}</p>")
                return
            code = (qs.get("code") or [""])[0]
            state = (qs.get("state") or [""])[0]
            if state not in oauth_state:
                self._send(400, "<h1>State inválido</h1><p>Reinicia el flujo desde /oauth/%s/start</p>" % provider)
                return
            oauth_state.pop(state, None)
            if code == "":
                self._send(400, "<h1>Falta 'code'</h1>")
                return
            try:
                if provider == "tiktok":
                    values = _tiktok_callback(settings, code=code, redirect_uri=base + "/callback/tiktok")
                else:
                    values = _meta_callback(settings, code=code, redirect_uri=base + "/callback/meta")
                path = set_env_vars(default_env_path(), values)
            except Exception as e:  # noqa: BLE001 - surface a readable page
                log.error("oauth %s callback failed: %s", provider, e)
                self._send(502, f"<h1>Fallo al intercambiar tokens ({escape(provider)})</h1><pre>{escape(str(e)[:800])}</pre>")
                return
            keys = ", ".join(sorted(values.keys()))
            self._send(200, f"<h1>OK ✅</h1><p>{escape(provider)} conectado. Guardado en <code>{escape(str(path))}</code>:</p><p>{escape(keys)}</p><p>Ya puedes cerrar esta pestaña.</p>")

        def do_GET(self) -> None:  # noqa: N802 - stdlib signature
            parsed = urlparse(self.path)
            route = parsed.path
            if route == "/healthz":
                self._send(200, "ok", content_type="text/plain; charset=utf-8")
                return
            if route in ("/oauth/tiktok/start", "/oauth/meta/start"):
                self._start_oauth("tiktok" if "tiktok" in route else "meta")
                return
            if route in ("/callback/tiktok", "/callback/meta"):
                self._handle_callback("tiktok" if "tiktok" in route else "meta", parse_qs(parsed.query))
                return
            super().do_GET()

    return Handler


def serve_assets(*, settings: Settings, port: int | None = None, public_base_url: str | None = None) -> None:
    out_dir = Path(settings.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    p = int(port) if port is not None else int(settings.asset_server_port)
    base = (public_base_url if public_base_url is not None else settings.public_base_url) or ""
    handler = _make_handler(settings=settings, directory=str(out_dir), public_base_url=base, oauth_state={})
    with socketserver.TCPServer(("0.0.0.0", p), handler) as httpd:
        log.info("serving assets on :%s (base=%s)", p, base.rstrip("/") or "(none)")
        httpd.serve_forever()
