from xai_automation.config.settings import load_settings


def _clear(monkeypatch) -> None:
    for k in ("LLM_PROVIDER", "GEMINI_MODEL", "DEEPSEEK_MODEL", "MAX_MODEL_OUTPUT_TOKENS", "HIGGSFIELD_ARG_NAME"):
        monkeypatch.delenv(k, raising=False)


def test_default_llm_is_gemini_with_valid_model(monkeypatch) -> None:
    _clear(monkeypatch)
    s = load_settings()
    assert s.llm_provider == "gemini"
    assert s.gemini_model == "gemini-2.5-flash"


def test_default_nvidia_model_is_namespaced(monkeypatch) -> None:
    _clear(monkeypatch)
    s = load_settings()
    assert s.deepseek_model == "deepseek-ai/deepseek-v3.1-terminus"


def test_default_output_tokens_large_enough_for_full_plan(monkeypatch) -> None:
    _clear(monkeypatch)
    s = load_settings()
    assert s.max_model_output_tokens >= 2000


def test_default_higgsfield_arg_name(monkeypatch) -> None:
    _clear(monkeypatch)
    s = load_settings()
    assert s.higgsfield_arg_name == "video_spec"
