from __future__ import annotations

import os
from pathlib import Path


def default_env_path() -> Path:
    """Resolve the .env file we should write to.

    Mirrors the search order of ``env_loader.load_dotenv_best_effort`` but, for
    writing, falls back to ``./.env`` (created on first write) when none exists.
    """
    explicit = os.environ.get("XAI_ENV_FILE", "").strip()
    if explicit:
        return Path(explicit)
    for candidate in (Path.cwd() / ".env", Path.cwd().parent / ".env"):
        if candidate.exists():
            return candidate
    return Path.cwd() / ".env"


def _is_assignment(line: str, key: str) -> bool:
    s = line.lstrip()
    if s.startswith("#"):
        return False
    head = s.split("=", 1)[0].strip() if "=" in s else ""
    return head == key


def set_env_vars(path: Path, values: dict[str, str]) -> Path:
    """Insert/update ``KEY=value`` pairs in ``path`` preserving comments and order.

    Existing keys are updated in place; missing keys are appended. Also updates
    ``os.environ`` so the running process sees the new values immediately.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)

    out: list[str] = []
    for line in lines:
        replaced = False
        for key in list(remaining.keys()):
            if _is_assignment(line, key):
                out.append(f"{key}={remaining.pop(key)}")
                replaced = True
                break
        if not replaced:
            out.append(line)

    for key, value in remaining.items():
        out.append(f"{key}={value}")

    text = "\n".join(out)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")

    for key, value in values.items():
        os.environ[key] = value

    return path
