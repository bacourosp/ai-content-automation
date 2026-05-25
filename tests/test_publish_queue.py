from __future__ import annotations

import xai_automation.workflows.publish_queue as pq
from xai_automation.config.settings import load_settings
from xai_automation.services.errors import ApiCallError

_PLAN = {
    "content_plan": {
        "facebook": {"post_long": "Post body", "cta": "Follow", "video": {"script": "vid script"}},
        "tiktok": {"caption": "Cap"},
        "instagram": {"caption": "Cap", "cta": "cta"},
    },
    "hook": "Hook",
}


def test_facebook_uses_single_video_call_when_video_present(tmp_path, monkeypatch) -> None:
    s = load_settings()
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00")
    calls = []

    class FakeFB:
        def __init__(self, cfg, *, timeout_seconds):
            pass

        def publish_video(self, *, video_path, description):
            calls.append(("video", description))

        def publish_text_post(self, *, message):
            calls.append(("text", message))

    monkeypatch.setattr(pq, "FacebookPublisher", FakeFB)
    pq._publish_facebook(settings=s, payload=_PLAN, video_path=video)
    assert calls == [("video", "Post body\n\nFollow")]


def test_facebook_text_only_when_no_video(tmp_path, monkeypatch) -> None:
    s = load_settings()
    calls = []

    class FakeFB:
        def __init__(self, cfg, *, timeout_seconds):
            pass

        def publish_video(self, *, video_path, description):
            calls.append(("video", description))

        def publish_text_post(self, *, message):
            calls.append(("text", message))

    monkeypatch.setattr(pq, "FacebookPublisher", FakeFB)
    pq._publish_facebook(settings=s, payload=_PLAN, video_path=tmp_path / "missing.mp4")
    assert calls == [("text", "Post body\n\nFollow")]


def test_tiktok_refreshes_token_on_401(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RETRY_MAX", "1")
    monkeypatch.setenv("RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "old")
    monkeypatch.setenv("TIKTOK_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "ck")
    s = load_settings()
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00")
    done = {"polled": False}

    class FakeTT:
        def __init__(self, cfg, *, timeout_seconds):
            self.token = cfg.access_token

        def init_video_publish(self, *, title, video_bytes):
            if self.token == "old":
                raise ApiCallError(provider="tiktok", method="POST", url="u", status_code=401, message="expired", request=None, response_text=None)
            return {"data": {"upload_url": "https://u", "publish_id": "pid"}}

        def upload_video(self, *, upload_url, video_path):
            pass

        def poll_until_done(self, *, publish_id, **kw):
            done["polled"] = True

    monkeypatch.setattr(pq, "TikTokPublisher", FakeTT)
    monkeypatch.setattr(pq, "_refresh_tiktok_token", lambda settings: "new")
    pq._publish_tiktok(settings=s, payload=_PLAN, video_path=video)
    assert done["polled"] is True
