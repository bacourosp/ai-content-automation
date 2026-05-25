from pathlib import Path

from xai_automation.config.env_writer import default_env_path, set_env_vars


def test_set_env_vars_updates_existing_and_appends_new(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("# comment\nFOO=old\nBAR=keep\n", encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)

    set_env_vars(env, {"FOO": "new", "BAZ": "added"})
    text = env.read_text(encoding="utf-8")

    assert "# comment" in text  # comments preserved
    assert "FOO=new" in text
    assert "FOO=old" not in text
    assert "BAR=keep" in text
    assert "BAZ=added" in text


def test_set_env_vars_creates_file_and_updates_environ(tmp_path, monkeypatch) -> None:
    env = tmp_path / "sub" / ".env"
    monkeypatch.delenv("HELLO", raising=False)
    set_env_vars(env, {"HELLO": "world"})
    assert env.exists()
    import os

    assert os.environ["HELLO"] == "world"


def test_default_env_path_honors_xai_env_file(tmp_path, monkeypatch) -> None:
    target = tmp_path / "custom.env"
    monkeypatch.setenv("XAI_ENV_FILE", str(target))
    assert default_env_path() == Path(str(target))
