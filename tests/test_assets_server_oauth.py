from __future__ import annotations

import http.client
import socket
import socketserver
import threading
import time
from contextlib import closing

import xai_automation.workflows.assets_server as mod
from xai_automation.config.settings import load_settings


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server:
    def __init__(self, handler, port: int) -> None:
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
        self.port = port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        for _ in range(50):
            try:
                with closing(socket.create_connection(("127.0.0.1", self.port), timeout=0.2)):
                    break
            except OSError:
                time.sleep(0.02)
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()

    def get(self, path: str):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        conn.request("GET", path)
        r = conn.getresponse()
        body = r.read()
        conn.close()
        return r.status, dict(r.getheaders()), body


def _make_server(tmp_path, monkeypatch, *, base: str, oauth_state: dict):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "ck")
    monkeypatch.setenv("META_APP_ID", "aid")
    s = load_settings()
    (tmp_path / "out").mkdir(parents=True, exist_ok=True)
    handler = mod._make_handler(settings=s, directory=str(tmp_path / "out"), public_base_url=base, oauth_state=oauth_state)
    return _Server(handler, _free_port())


def test_healthz(tmp_path, monkeypatch) -> None:
    with _make_server(tmp_path, monkeypatch, base="https://x.dev", oauth_state={}) as srv:
        status, _, body = srv.get("/healthz")
        assert status == 200
        assert body == b"ok"


def test_oauth_start_redirects(tmp_path, monkeypatch) -> None:
    with _make_server(tmp_path, monkeypatch, base="https://x.dev", oauth_state={}) as srv:
        status, headers, _ = srv.get("/oauth/meta/start")
        assert status == 302
        assert "facebook.com" in headers["Location"]


def test_oauth_start_without_base_is_400(tmp_path, monkeypatch) -> None:
    with _make_server(tmp_path, monkeypatch, base="", oauth_state={}) as srv:
        status, _, _ = srv.get("/oauth/tiktok/start")
        assert status == 400


def test_callback_invalid_state_is_400(tmp_path, monkeypatch) -> None:
    with _make_server(tmp_path, monkeypatch, base="https://x.dev", oauth_state={}) as srv:
        status, _, _ = srv.get("/callback/meta?code=abc&state=nope")
        assert status == 400


def test_callback_success_writes_env(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    monkeypatch.setenv("XAI_ENV_FILE", str(env))
    monkeypatch.setattr(mod, "_meta_callback", lambda settings, *, code, redirect_uri: {"META_ACCESS_TOKEN": "AT"})
    state = "known-state"
    with _make_server(tmp_path, monkeypatch, base="https://x.dev", oauth_state={state: 0.0}) as srv:
        status, _, body = srv.get(f"/callback/meta?code=abc&state={state}")
        assert status == 200
        assert b"OK" in body
    assert "META_ACCESS_TOKEN=AT" in env.read_text(encoding="utf-8")


def test_static_asset_served(tmp_path, monkeypatch) -> None:
    with _make_server(tmp_path, monkeypatch, base="https://x.dev", oauth_state={}) as srv:
        d = tmp_path / "out" / "assets" / "J"
        d.mkdir(parents=True, exist_ok=True)
        (d / "video.mp4").write_bytes(b"\x00\x01\x02")
        status, _, body = srv.get("/assets/J/video.mp4")
        assert status == 200
        assert body == b"\x00\x01\x02"
