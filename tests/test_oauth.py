from urllib.parse import parse_qs, urlparse

from xai_automation.connectors.oauth_meta import MetaOAuth, MetaOAuthConfig, meta_authorize_url
from xai_automation.connectors.oauth_tiktok import TikTokOAuth, TikTokOAuthConfig, tiktok_authorize_url


def test_tiktok_authorize_url_has_required_params() -> None:
    u = tiktok_authorize_url(client_key="ck", redirect_uri="https://x.dev/callback/tiktok", state="st")
    q = parse_qs(urlparse(u).query)
    assert q["client_key"] == ["ck"]
    assert q["response_type"] == ["code"]
    assert q["redirect_uri"] == ["https://x.dev/callback/tiktok"]
    assert q["state"] == ["st"]
    assert "video.publish" in q["scope"][0]


def test_meta_authorize_url_has_required_params() -> None:
    u = meta_authorize_url(app_id="aid", redirect_uri="https://x.dev/callback/meta", state="st", api_version="v19.0")
    assert u.startswith("https://www.facebook.com/v19.0/dialog/oauth?")
    q = parse_qs(urlparse(u).query)
    assert q["client_id"] == ["aid"]
    assert q["response_type"] == ["code"]
    assert "instagram_content_publish" in q["scope"][0]


def test_tiktok_exchange_code_posts_form(monkeypatch) -> None:
    oa = TikTokOAuth(TikTokOAuthConfig(client_key="ck", client_secret="cs"))
    captured = {}

    def _fake_post_form(url, *, data, headers=None, provider="http"):
        captured["url"] = url
        captured["data"] = data
        return {"access_token": "AT", "refresh_token": "RT", "expires_in": 86400}

    monkeypatch.setattr(oa._http, "post_form", _fake_post_form)
    tok = oa.exchange_code(code="abc", redirect_uri="https://x.dev/callback/tiktok")
    assert tok["access_token"] == "AT"
    assert captured["url"].endswith("/v2/oauth/token/")
    assert captured["data"]["grant_type"] == "authorization_code"
    assert captured["data"]["code"] == "abc"


def test_meta_exchange_code_uses_get(monkeypatch) -> None:
    oa = MetaOAuth(MetaOAuthConfig(app_id="aid", app_secret="sec", api_version="v19.0"))
    captured = {}

    def _fake_get_json(url, *, headers=None, params=None, provider="http"):
        captured["url"] = url
        captured["params"] = params
        return {"access_token": "SHORT"}

    monkeypatch.setattr(oa._http, "get_json", _fake_get_json)
    tok = oa.exchange_code(code="xyz", redirect_uri="https://x.dev/callback/meta")
    assert tok["access_token"] == "SHORT"
    assert captured["params"]["code"] == "xyz"
    assert captured["url"].endswith("/oauth/access_token")
