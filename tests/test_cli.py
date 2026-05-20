import json

import pytest

from xai_automation.cli import main


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

