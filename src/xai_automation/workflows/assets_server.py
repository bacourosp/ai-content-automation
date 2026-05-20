from __future__ import annotations

import http.server
import socketserver
from functools import partial
from pathlib import Path

from xai_automation.config.settings import Settings


def serve_assets(*, settings: Settings, port: int | None = None) -> None:
    out_dir = Path(settings.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    p = int(port) if port is not None else int(settings.asset_server_port)
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(out_dir))
    with socketserver.TCPServer(("0.0.0.0", p), handler) as httpd:
        httpd.serve_forever()
