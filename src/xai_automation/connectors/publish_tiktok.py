from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


log = logging.getLogger("xai_automation.publish_tiktok")


class TikTokPublishError(RuntimeError):
    pass


@dataclass(frozen=True)
class TikTokConfig:
    access_token: str
    api_base: str = "https://open.tiktokapis.com"


class TikTokPublisher:
    def __init__(self, cfg: TikTokConfig, *, timeout_seconds: int):
        self._cfg = cfg
        self._timeout = timeout_seconds

    def init_video_publish(self, *, title: str, video_bytes: int) -> dict[str, Any]:
        if self._cfg.access_token.strip() == "":
            raise TikTokPublishError("missing tiktok access token")
        url = f"{self._cfg.api_base.rstrip('/')}/v2/post/publish/video/init/"
        payload = {
            "post_info": {"title": title[:90]},
            "source_info": {"source": "FILE_UPLOAD", "video_size": int(video_bytes), "chunk_size": int(video_bytes), "total_chunk_count": 1},
        }
        headers = {"Authorization": f"Bearer {self._cfg.access_token}", "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False), timeout=self._timeout)
        if r.status_code >= 400:
            raise TikTokPublishError(f"{r.status_code} {r.text[:500]}")
        return r.json()

    def upload_video(self, *, upload_url: str, video_path: Path) -> None:
        if not video_path.exists():
            raise TikTokPublishError("video file missing")
        with video_path.open("rb") as f:
            data = f.read()
        r = requests.put(upload_url, data=data, timeout=self._timeout)
        if r.status_code >= 400:
            raise TikTokPublishError(f"upload failed: {r.status_code} {r.text[:200]}")

    def fetch_publish_status(self, *, publish_id: str) -> dict[str, Any]:
        url = f"{self._cfg.api_base.rstrip('/')}/v2/post/publish/status/fetch/"
        payload = {"publish_id": publish_id}
        headers = {"Authorization": f"Bearer {self._cfg.access_token}", "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False), timeout=self._timeout)
        if r.status_code >= 400:
            raise TikTokPublishError(f"{r.status_code} {r.text[:500]}")
        return r.json()
