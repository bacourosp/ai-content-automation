from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from xai_automation.services.errors import ApiCallError


log = logging.getLogger("xai_automation.publish_tiktok")


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
            raise ApiCallError(
                provider="tiktok",
                method="POST",
                url=self._cfg.api_base.rstrip("/") + "/v2/post/publish/video/init/",
                status_code=None,
                message="missing tiktok access token",
                request=None,
                response_text=None,
            )
        url = f"{self._cfg.api_base.rstrip('/')}/v2/post/publish/video/init/"
        payload = {
            "post_info": {"title": title[:90]},
            "source_info": {"source": "FILE_UPLOAD", "video_size": int(video_bytes), "chunk_size": int(video_bytes), "total_chunk_count": 1},
        }
        headers = {"Authorization": f"Bearer {self._cfg.access_token}", "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False), timeout=self._timeout)
        if r.status_code >= 400:
            raise ApiCallError(
                provider="tiktok",
                method="POST",
                url=url,
                status_code=int(r.status_code),
                message=f"{r.status_code} {r.text[:500]}",
                request={"headers": headers, "payload": payload},
                response_text=r.text,
            )
        return r.json()

    def upload_video(self, *, upload_url: str, video_path: Path) -> None:
        if not video_path.exists():
            raise ApiCallError(
                provider="tiktok",
                method="PUT",
                url=upload_url,
                status_code=None,
                message="video file missing",
                request={"video_path": str(video_path)},
                response_text=None,
            )
        with video_path.open("rb") as f:
            data = f.read()
        r = requests.put(upload_url, data=data, timeout=self._timeout)
        if r.status_code >= 400:
            raise ApiCallError(
                provider="tiktok",
                method="PUT",
                url=upload_url,
                status_code=int(r.status_code),
                message=f"upload failed: {r.status_code} {r.text[:200]}",
                request={"bytes": len(data)},
                response_text=r.text,
            )

    def fetch_publish_status(self, *, publish_id: str) -> dict[str, Any]:
        url = f"{self._cfg.api_base.rstrip('/')}/v2/post/publish/status/fetch/"
        payload = {"publish_id": publish_id}
        headers = {"Authorization": f"Bearer {self._cfg.access_token}", "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False), timeout=self._timeout)
        if r.status_code >= 400:
            raise ApiCallError(
                provider="tiktok",
                method="POST",
                url=url,
                status_code=int(r.status_code),
                message=f"{r.status_code} {r.text[:500]}",
                request={"headers": headers, "payload": payload},
                response_text=r.text,
            )
        return r.json()
