from __future__ import annotations

from types import SimpleNamespace

from xai_automation.config.settings import load_settings
from xai_automation.workflows.assets_server import serve_assets


def test_assets_server_binds_configured_port(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("ASSET_SERVER_PORT", "9098")
    s = load_settings()

    bound = {}

    class _FakeTCP:
        def __init__(self, addr, handler):
            bound["addr"] = addr
            bound["handler"] = handler

        def __enter__(self):
            return SimpleNamespace(serve_forever=lambda: None)

        def __exit__(self, exc_type, exc, tb):
            return False

    import xai_automation.workflows.assets_server as mod

    monkeypatch.setattr(mod.socketserver, "TCPServer", _FakeTCP)
    serve_assets(settings=s, port=None)
    assert bound["addr"][1] == 9098

