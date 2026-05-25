from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from xai_automation.services.http import HttpClient

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"


def tiktok_authorize_url(*, client_key: str, redirect_uri: str, state: str, scope: str = "video.publish,video.upload") -> str:
    params = {
        "client_key": client_key,
        "scope": scope,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return AUTHORIZE_URL + "?" + urlencode(params)


@dataclass(frozen=True)
class TikTokOAuthConfig:
    client_key: str
    client_secret: str
    api_base: str = "https://open.tiktokapis.com"


class TikTokOAuth:
    """Exchanges/refreshes TikTok OAuth v2 tokens (Content Posting API)."""

    def __init__(self, cfg: TikTokOAuthConfig, *, timeout_seconds: int = 30):
        self._cfg = cfg
        self._http = HttpClient(timeout_seconds=timeout_seconds)

    def _token_url(self) -> str:
        return self._cfg.api_base.rstrip("/") + "/v2/oauth/token/"

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict[str, Any]:
        data = {
            "client_key": self._cfg.client_key,
            "client_secret": self._cfg.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        return self._http.post_form(self._token_url(), data=data, provider="tiktok")

    def refresh(self, *, refresh_token: str) -> dict[str, Any]:
        data = {
            "client_key": self._cfg.client_key,
            "client_secret": self._cfg.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        return self._http.post_form(self._token_url(), data=data, provider="tiktok")
