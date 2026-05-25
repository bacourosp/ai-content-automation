from xai_automation.config.settings import load_settings


def test_settings_reads_llm_provider_gemini(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-flash")
    s = load_settings()
    assert s.llm_provider == "gemini"
    assert s.gemini_api_key == "k"

