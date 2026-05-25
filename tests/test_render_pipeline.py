from __future__ import annotations

from pathlib import Path

from xai_automation.config.settings import load_settings
from xai_automation.storage.db import Database
from xai_automation.workflows.pipeline import run_once

_SB = [{"t": 0, "duration": 5, "on_screen_text": "A", "voiceover": "B", "visual": "C", "broll": "D"}]


def _score() -> dict:
    return {
        "topic_score": 80,
        "category": "ai_news",
        "viral_angle": "v",
        "hook": "Hook",
        "audience": "a",
        "visual_style": "clean tech",
        "content_plan": {
            "tiktok": {"seconds": 25, "hook": "H", "script": "S", "storyboard": _SB, "caption": "Cap", "hashtags": ["#ai"], "shot_list": ["s"], "broll_suggestions": ["b"]},
            "instagram": {"reel": {"seconds": 25, "hook": "H", "script": "S", "storyboard": _SB}, "caption": "Cap", "cta": "CTA", "hashtags": ["#ai"], "carousel": {"enabled": False, "slides": []}},
            "facebook": {"post_long": "P", "cta": "CTA", "hashtags": ["#ai"], "video": {"seconds": 25, "hook": "H", "script": "S", "storyboard": _SB}},
        },
    }


def test_pipeline_uses_alternate_render_provider(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "data" / "app.db"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path / "out" / "assets"))
    monkeypatch.setenv("X_BEARER_TOKEN", "x")
    monkeypatch.setenv("X_SOURCES", "search")
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", "n")
    monkeypatch.setenv("REQUIRE_APPROVAL", "true")
    # Alternate render provider (generic HTTP MCP), stubbed below.
    monkeypatch.setenv("RENDER_PROVIDER", "mcp")
    monkeypatch.setenv("RENDER_MCP_URL", "http://localhost:9999/mcp")
    monkeypatch.setenv("RENDER_COST_PER_VIDEO_USD", "0.10")

    import xai_automation.workflows.pipeline as pmod
    from xai_automation.connectors.x_api import XPost

    class _FakeX:
        def __init__(self, bearer_token: str, timeout_seconds: int):
            pass

        def fetch_recent_search(self, *, query, since_id, max_results, languages):
            return ([XPost(id="100", author_handle="a", created_at="2026-01-01T00:00:00Z", text="OpenAI shipped a new model.", url="https://x.com/a/status/100", lang="en")], "100")

    class _FakeDeepSeek:
        def __init__(self, cfg):
            pass

        def score_post(self, *, prompt, post_payload):
            return _score()

    class _FakeRenderer:
        def render_video(self, *, video_spec):
            return {"video_path": str(tmp_path / "video.mp4")}

        def download_if_url(self, *, maybe_url, out_path):
            raise RuntimeError("should not be called")

    (tmp_path / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")

    monkeypatch.setattr(pmod, "XApiClient", _FakeX)
    monkeypatch.setattr(pmod, "DeepSeekClient", _FakeDeepSeek)
    monkeypatch.setattr(pmod, "build_render_provider", lambda settings: _FakeRenderer())

    s = load_settings()
    db = Database(s.sqlite_path)
    db.init()
    run_once(settings=s, db=db)

    with db.connect() as con:
        job = con.execute("SELECT state FROM jobs LIMIT 1").fetchone()
        assert str(job["state"]) == "queued"
        ce = con.execute("SELECT provider, cost_usd FROM cost_events LIMIT 1").fetchone()
        assert str(ce["provider"]) == "mcp"
        assert abs(float(ce["cost_usd"]) - 0.10) < 1e-9
