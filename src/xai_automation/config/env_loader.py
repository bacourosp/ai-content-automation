from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def load_dotenv_best_effort() -> list[Path]:
    loaded: list[Path] = []

    explicit = os.environ.get("XAI_ENV_FILE", "").strip()
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))

    candidates.extend([
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
        Path("/etc/xai-automation/xai.env"),
        Path.home() / ".config" / "xai-automation" / "xai.env",
    ])

    for p in candidates:
        if p.exists():
            load_dotenv(p, override=False)
            loaded.append(p)

    return loaded


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)
