from __future__ import annotations

import json
from pathlib import Path

from xai_automation.config.settings import load_settings
from xai_automation.storage.db import Database
from xai_automation.workflows.pipeline import run_once


def test_pipeline_e2e_stubbed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "data" / "app.db"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path / "out" / "assets"))
    monkeypatch.setenv("X_BEARER_TOKEN", "x")
    monkeypatch.setenv("X_SOURCES", "search")
    monkeypatch.setenv("NVIDIA_API_KEY", "n")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-prod")
    monkeypatch.setenv("HIGGSFIELD_MCP_URL", "http://localhost:1234")
    monkeypatch.setenv("HIGGSFIELD_API_KEY", "h")
    monkeypatch.setenv("REQUIRE_APPROVAL", "true")

    import xai_automation.workflows.pipeline as pmod

    class _FakeX:
        def __init__(self, bearer_token: str, timeout_seconds: int):
            pass

        def fetch_recent_search(self, *, query: str, since_id: str | None, max_results: int, languages: list[str]):
            from xai_automation.connectors.x_api import XPost

            return (
                [
                    XPost(
                        id="100",
                        author_handle="someone",
                        created_at="2026-01-01T00:00:00Z",
                        text="OpenAI released a new model for coding.",
                        url="https://x.com/someone/status/100",
                        lang="en",
                    )
                ],
                "100",
            )

    class _FakeDeepSeek:
        def __init__(self, cfg):
            pass

        def score_post(self, *, prompt: str, post_payload: dict[str, str]):
            return {
                "topic_score": 80,
                "category": "ai_news",
                "viral_angle": "fast update",
                "hook": "New model drop",
                "audience": "builders",
                "visual_style": "clean tech",
                "content_plan": {
                    "tiktok": {
                        "seconds": 25,
                        "hook": "Hook",
                        "script": "Script",
                        "storyboard": [
                            {
                                "t": 0,
                                "duration": 5,
                                "on_screen_text": "A",
                                "voiceover": "B",
                                "visual": "C",
                                "broll": "D",
                            }
                        ],
                        "caption": "Cap",
                        "hashtags": ["#ai"],
                        "shot_list": ["Shot 1"],
                        "broll_suggestions": ["Broll 1"],
                    },
                    "instagram": {
                        "reel": {
                            "seconds": 25,
                            "hook": "Hook",
                            "script": "Script",
                            "storyboard": [
                                {
                                    "t": 0,
                                    "duration": 5,
                                    "on_screen_text": "A",
                                    "voiceover": "B",
                                    "visual": "C",
                                    "broll": "D",
                                }
                            ],
                        },
                        "caption": "Cap",
                        "cta": "CTA",
                        "hashtags": ["#ai"],
                        "carousel": {"enabled": False, "slides": []},
                    },
                    "facebook": {
                        "post_long": "Post",
                        "cta": "CTA",
                        "hashtags": ["#ai"],
                        "video": {
                            "seconds": 25,
                            "hook": "Hook",
                            "script": "Script",
                            "storyboard": [
                                {
                                    "t": 0,
                                    "duration": 5,
                                    "on_screen_text": "A",
                                    "voiceover": "B",
                                    "visual": "C",
                                    "broll": "D",
                                }
                            ],
                        },
                    },
                },
            }

    class _FakeHiggsfield:
        def __init__(self, cfg):
            pass

        def render_video(self, *, video_spec: dict):
            return {"video_path": str(tmp_path / "video.mp4")}

        def download_if_url(self, *, maybe_url: str, out_path: Path):
            raise RuntimeError("should not be called")

    monkeypatch.setattr(pmod, "XApiClient", _FakeX)
    monkeypatch.setattr(pmod, "DeepSeekClient", _FakeDeepSeek)
    monkeypatch.setattr(pmod, "HiggsfieldClient", _FakeHiggsfield)

    (tmp_path / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")

    s = load_settings()
    db = Database(s.sqlite_path)
    db.init()
    run_once(settings=s, db=db)

    with db.connect() as con:
        jobs = con.execute("SELECT state FROM jobs").fetchall()
        assert len(jobs) == 1
        assert jobs[0]["state"] == "queued"
        q = con.execute("SELECT platform, status, payload_json FROM publish_queue").fetchall()
        assert len(q) == 3
        for row in q:
            assert row["status"] == "awaiting_approval"
            payload = json.loads(row["payload_json"])
            assert payload["topic_score"] == 80

