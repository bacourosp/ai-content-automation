from xai_automation.services.gemini import GeminiClient, GeminiConfig


def test_gemini_ping_parses_ok(monkeypatch) -> None:
    cfg = GeminiConfig(api_key="k", model="gemini-1.5-flash", timeout_seconds=5)
    c = GeminiClient(cfg)

    def _fake_post_json(url, headers=None, payload=None, **kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "{\"ok\":true}"}]}}]}

    monkeypatch.setattr(c._http, "post_json", _fake_post_json)
    out = c.ping()
    assert out["ok"] is True
