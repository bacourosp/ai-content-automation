from pathlib import Path

from xai_automation.config.settings import load_settings
from xai_automation.storage.db import Database


def test_load_settings_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "data" / "app.db"))
    s = load_settings()
    assert s.sqlite_path.name == "app.db"


def test_db_init_smoke(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    db.init()
    with db.connect() as con:
        r = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='posts'").fetchone()
        assert r is not None
