from xai_automation.config.settings import load_settings


def test_settings_reads_asset_server_port(monkeypatch) -> None:
    monkeypatch.setenv("ASSET_SERVER_PORT", "9099")
    s = load_settings()
    assert s.asset_server_port == 9099

