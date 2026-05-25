from xai_automation.config.settings import load_settings
from xai_automation.workflows.preflight import run_preflight


def test_preflight_no_network_reports_missing(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)  # default provider is now "gemini"
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("HIGGSFIELD_MCP_URL", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_KEY", raising=False)
    s = load_settings()
    r = run_preflight(settings=s, network=False)
    assert r["ok"] is False
    assert "env.gemini_api_key" in r["errors"]
