"""Compat wrapper: imprime el reporte de setup (URLs/callbacks/checklist).

El camino canónico ahora es el CLI:
    xai-automation init-system [--write-env]
    xai-automation serve-assets   (levanta tunnel + escribe PUBLIC_BASE_URL + OAuth)

Este script se mantiene para `python3 scripts/init_system.py`.
"""
from __future__ import annotations

import sys

from xai_automation.config.settings import load_settings
from xai_automation.services.callback_urls import normalize_base_url
from xai_automation.services.logging import configure_logging
from xai_automation.storage.db import Database
from xai_automation.workflows.setup_report import build_setup_report


def main() -> int:
    s = load_settings()
    configure_logging(s.log_level)
    Database(s.sqlite_path).init()
    public = normalize_base_url(s.public_base_url)
    sys.stdout.write(build_setup_report(settings=s, public_base_url=public) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
