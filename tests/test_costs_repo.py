from datetime import datetime, timezone
from pathlib import Path

from xai_automation.storage.db import Database
from xai_automation.storage.repo import Repo


def test_cost_event_and_monthly_total(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    db.init()
    repo = Repo(db)

    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    repo.add_cost_event(provider="higgsfield", job_id="j1", asset_id="a1", month_key=month_key, cost_usd=0.25, units=1, details={"k": "v"})
    repo.add_cost_event(provider="higgsfield", job_id="j2", asset_id="a2", month_key=month_key, cost_usd=0.40, units=1, details={})

    total = repo.get_monthly_cost_total(provider="higgsfield", month_key=month_key)
    assert abs(total - 0.65) < 1e-9

