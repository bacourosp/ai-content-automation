import json

import pytest

from xai_automation.cli import main
from xai_automation.services.errors import ApiCallError
from xai_automation.storage.db import Database
from xai_automation.storage.repo import Repo


def test_cli_print_config_exits_0(capsys, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", "./data/app.db")
    with pytest.raises(SystemExit) as e:
        main(["print-config"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "APP_NAME=" in out


def test_cli_preflight_no_network_outputs_json(capsys, monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(SystemExit) as e:
        main(["preflight", "--no-network"])
    assert e.value.code == 2
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["ok"] is False


def test_cli_costs_outputs_json(tmp_path, capsys, monkeypatch) -> None:
    db = Database(tmp_path / "app.db")
    db.init()
    repo = Repo(db)
    repo.add_cost_event(provider="higgsfield", job_id="j1", asset_id="a1", month_key="2026-01", cost_usd=0.5, units=1, details={})

    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "app.db"))
    with pytest.raises(SystemExit) as e:
        main(["costs", "--month", "2026-01"])
    assert e.value.code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["provider"] == "higgsfield"
    assert abs(payload["total_usd"] - 0.5) < 1e-9


def test_cli_errors_list_and_show(tmp_path, capsys, monkeypatch) -> None:
    db = Database(tmp_path / "app.db")
    db.init()
    repo = Repo(db)
    eid = repo.log_api_error(
        job_id="j1",
        asset_id="a1",
        err=ApiCallError(
            provider="higgsfield",
            method="POST",
            url="https://mcp.higgsfield.ai/mcp",
            status_code=429,
            message="quota exceeded",
            request={"headers": {"Authorization": "Bearer s"}},
            response_text="{}",
        ),
    )

    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "app.db"))
    with pytest.raises(SystemExit) as e1:
        main(["errors", "--provider", "higgsfield", "--limit", "10"])
    assert e1.value.code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert len(payload["errors"]) == 1
    assert payload["errors"][0]["id"] == eid

    with pytest.raises(SystemExit) as e2:
        main(["error", "--id", eid])
    assert e2.value.code == 0
    row = json.loads(capsys.readouterr().out.strip())
    assert row["id"] == eid
