from xai_automation.config.settings import load_settings


def test_settings_higgsfield_api_key_falls_back_to_secret(monkeypatch) -> None:
    monkeypatch.delenv("HIGGSFIELD_API_KEY", raising=False)
    monkeypatch.setenv("HIGGSFIELD_API_KEY_SECRET", "s")
    s = load_settings()
    assert s.higgsfield_api_key == "s"

