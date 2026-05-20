from xai_automation.config.settings import load_settings
from xai_automation.workflows.preflight import run_preflight


def test_preflight_no_network_reports_missing(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("HIGGSFIELD_MCP_URL", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_KEY", raising=False)
    s = load_settings()
    r = run_preflight(settings=s, network=False)
    assert r["ok"] is False
    assert "env.nvidia_api_key" in r["errors"]

