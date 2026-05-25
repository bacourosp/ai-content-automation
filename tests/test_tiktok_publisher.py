import pytest

from xai_automation.connectors.publish_tiktok import TikTokConfig, TikTokPublisher
from xai_automation.services.errors import ApiCallError


def _pub() -> TikTokPublisher:
    return TikTokPublisher(TikTokConfig(access_token="t", api_base="https://open.tiktokapis.com"), timeout_seconds=5)


def test_init_validates_response_shape(monkeypatch) -> None:
    p = _pub()
    monkeypatch.setattr(p._http, "post_json", lambda *a, **k: {"data": {}})  # missing upload_url/publish_id
    with pytest.raises(ApiCallError):
        p.init_video_publish(title="hi", video_bytes=1000)


def test_init_accepts_valid_response(monkeypatch) -> None:
    p = _pub()
    monkeypatch.setattr(p._http, "post_json", lambda *a, **k: {"data": {"upload_url": "https://u", "publish_id": "pid"}})
    out = p.init_video_publish(title="hi", video_bytes=1000)
    assert out["data"]["publish_id"] == "pid"


def test_poll_until_done_success(monkeypatch) -> None:
    p = _pub()
    seq = iter([
        {"data": {"status": "PROCESSING_UPLOAD"}},
        {"data": {"status": "PUBLISH_COMPLETE"}},
    ])
    monkeypatch.setattr(p, "fetch_publish_status", lambda *, publish_id: next(seq))
    monkeypatch.setattr("xai_automation.connectors.publish_tiktok.time.sleep", lambda *_a, **_k: None)
    res = p.poll_until_done(publish_id="pid", max_attempts=5, interval_seconds=0)
    assert res["data"]["status"] == "PUBLISH_COMPLETE"


def test_poll_until_done_failure_raises(monkeypatch) -> None:
    p = _pub()
    monkeypatch.setattr(p, "fetch_publish_status", lambda *, publish_id: {"data": {"status": "FAILED"}})
    monkeypatch.setattr("xai_automation.connectors.publish_tiktok.time.sleep", lambda *_a, **_k: None)
    with pytest.raises(ApiCallError):
        p.poll_until_done(publish_id="pid", max_attempts=5, interval_seconds=0)
