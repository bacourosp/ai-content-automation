import json
from pathlib import Path

from xai_automation.services.errors import ApiCallError, redact_secrets
from xai_automation.storage.db import Database
from xai_automation.storage.repo import Repo


def test_redact_secrets_masks_auth() -> None:
    payload = {
        "headers": {"Authorization": "Bearer secret", "X-API-KEY": "k"},
        "body": {"api_key": "nvapi-xxx", "token": "t"},
    }
    out = redact_secrets(payload)
    assert out["headers"]["Authorization"] != "Bearer secret"
    assert out["headers"]["X-API-KEY"] != "k"
    assert out["body"]["api_key"] != "nvapi-xxx"
    assert out["body"]["token"] != "t"


def test_repo_logs_api_error(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    db.init()
    repo = Repo(db)

    e = ApiCallError(
        provider="higgsfield",
        method="POST",
        url="https://mcp.higgsfield.ai/mcp",
        status_code=429,
        message="quota exceeded",
        request={"headers": {"Authorization": "Bearer s"}},
        response_text="{}",
    )
    err_id = repo.log_api_error(job_id="j1", asset_id="a1", err=e)
    row = repo.get_api_error(err_id)
    assert row["provider"] == "higgsfield"
    assert row["status_code"] == 429
    assert row["is_quota"] == 1
    req = json.loads(row["request_json"])
    assert req["headers"]["Authorization"] != "Bearer s"

