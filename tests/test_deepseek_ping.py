from xai_automation.services.deepseek import DeepSeekClient, DeepSeekConfig


def test_deepseek_ping_parses_minimal_json(monkeypatch) -> None:
    cfg = DeepSeekConfig(
        api_key="k",
        base_url="https://integrate.api.nvidia.com/v1",
        model="deepseek-v4-prod",
        timeout_seconds=5,
        max_output_tokens=16,
    )
    c = DeepSeekClient(cfg)

    def _fake_post_json(url, headers, payload):
        return {"choices": [{"message": {"content": "{\"ok\":true}"}}]}

    monkeypatch.setattr(c._http, "post_json", _fake_post_json)
    out = c.ping()
    assert out["ok"] is True

