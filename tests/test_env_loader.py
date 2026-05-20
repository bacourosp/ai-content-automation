from pathlib import Path

from xai_automation.config.env_loader import load_dotenv_best_effort, env


def test_env_loader_supports_explicit_env_file(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "xai.env"
    p.write_text("FOO=bar baz\n", encoding="utf-8")
    monkeypatch.setenv("XAI_ENV_FILE", str(p))
    load_dotenv_best_effort()
    assert env("FOO") == "bar baz"

