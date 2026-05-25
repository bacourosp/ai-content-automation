from xai_automation.config.settings import load_settings


def test_settings_reads_cloudflare_tunnel_vars(monkeypatch) -> None:
    monkeypatch.setenv("ASSET_SERVER_PORT", "8088")
    monkeypatch.setenv("WEBHOOK_PORT", "9090")
    monkeypatch.setenv("ENABLE_CLOUDFLARE_TUNNEL", "true")
    monkeypatch.setenv("CLOUDFLARE_TUNNEL_TOKEN", "tok")
    s = load_settings()
    assert s.webhook_port == 9090
    assert s.enable_cloudflare_tunnel is True
    assert s.cloudflare_tunnel_token == "tok"

