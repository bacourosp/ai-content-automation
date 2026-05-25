from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from xai_automation.services.http import HttpClient

DEFAULT_SCOPES = (
    "instagram_basic,instagram_content_publish,pages_show_list,"
    "pages_read_engagement,pages_manage_posts,business_management"
)


def meta_authorize_url(*, app_id: str, redirect_uri: str, state: str, scope: str = DEFAULT_SCOPES, api_version: str = "v19.0") -> str:
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": scope,
        "response_type": "code",
    }
    return f"https://www.facebook.com/{api_version}/dialog/oauth?" + urlencode(params)


@dataclass(frozen=True)
class MetaOAuthConfig:
    app_id: str
    app_secret: str
    api_version: str = "v19.0"


class MetaOAuth:
    """Meta (Facebook/Instagram) OAuth + page/IG-account resolution via Graph API."""

    def __init__(self, cfg: MetaOAuthConfig, *, timeout_seconds: int = 30):
        self._cfg = cfg
        self._http = HttpClient(timeout_seconds=timeout_seconds)
        self._base = f"https://graph.facebook.com/{cfg.api_version}"

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict[str, Any]:
        params = {
            "client_id": self._cfg.app_id,
            "redirect_uri": redirect_uri,
            "client_secret": self._cfg.app_secret,
            "code": code,
        }
        return self._http.get_json(self._base + "/oauth/access_token", params=params, provider="meta")

    def exchange_long_lived(self, *, short_token: str) -> dict[str, Any]:
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self._cfg.app_id,
            "client_secret": self._cfg.app_secret,
            "fb_exchange_token": short_token,
        }
        return self._http.get_json(self._base + "/oauth/access_token", params=params, provider="meta")

    def list_pages(self, *, user_token: str) -> list[dict[str, Any]]:
        params = {"access_token": user_token, "fields": "id,name,access_token"}
        j = self._http.get_json(self._base + "/me/accounts", params=params, provider="meta")
        data = j.get("data") if isinstance(j, dict) else None
        return data if isinstance(data, list) else []

    def get_ig_business_account(self, *, page_id: str, page_token: str) -> str:
        params = {"access_token": page_token, "fields": "instagram_business_account"}
        j = self._http.get_json(f"{self._base}/{page_id}", params=params, provider="meta")
        iba = j.get("instagram_business_account") if isinstance(j, dict) else None
        if isinstance(iba, dict):
            return str(iba.get("id") or "")
        return ""
