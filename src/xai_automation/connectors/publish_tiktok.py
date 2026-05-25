from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xai_automation.services.errors import ApiCallError
from xai_automation.services.http import HttpClient


log = logging.getLogger("xai_automation.publish_tiktok")

# Terminal statuses for the Content Posting API status/fetch endpoint.
_SUCCESS_STATUSES = {"PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"}
_FAILURE_STATUSES = {"FAILED"}


@dataclass(frozen=True)
class TikTokConfig:
    access_token: str
    api_base: str = "https://open.tiktokapis.com"


class TikTokPublisher:
    def __init__(self, cfg: TikTokConfig, *, timeout_seconds: int):
        self._cfg = cfg
        self._timeout = timeout_seconds
        self._http = HttpClient(timeout_seconds=timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._cfg.access_token}"}

    def _require_token(self, *, method: str, url: str) -> None:
        if self._cfg.access_token.strip() == "":
            raise ApiCallError(
                provider="tiktok",
                method=method,
                url=url,
                status_code=None,
                message="missing tiktok access token",
                request=None,
                response_text=None,
            )

    def init_video_publish(self, *, title: str, video_bytes: int) -> dict[str, Any]:
        url = f"{self._cfg.api_base.rstrip('/')}/v2/post/publish/video/init/"
        self._require_token(method="POST", url=url)
        size = int(video_bytes)
        payload = {
            "post_info": {"title": title[:90]},
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            },
        }
        j = self._http.post_json(url, headers=self._headers(), payload=payload, provider="tiktok")
        data = j.get("data") if isinstance(j, dict) else None
        if not isinstance(data, dict) or not str(data.get("upload_url") or "") or not str(data.get("publish_id") or ""):
            raise ApiCallError(
                provider="tiktok",
                method="POST",
                url=url,
                status_code=None,
                message=f"init response missing data.upload_url/publish_id: {j}",
                request={"payload": payload},
                response_text=None,
            )
        return j

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
        data = video_path.read_bytes()
        size = len(data)
        headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{size - 1}/{size}",
        }
        self._http.put_bytes(upload_url, data=data, headers=headers, provider="tiktok")

    def fetch_publish_status(self, *, publish_id: str) -> dict[str, Any]:
        url = f"{self._cfg.api_base.rstrip('/')}/v2/post/publish/status/fetch/"
        self._require_token(method="POST", url=url)
        payload = {"publish_id": publish_id}
        return self._http.post_json(url, headers=self._headers(), payload=payload, provider="tiktok")

    def poll_until_done(self, *, publish_id: str, max_attempts: int = 20, interval_seconds: int = 5) -> dict[str, Any]:
        last: dict[str, Any] = {}
        for _ in range(max(1, max_attempts)):
            last = self.fetch_publish_status(publish_id=publish_id)
            data = last.get("data") if isinstance(last, dict) else None
            status = str((data or {}).get("status") or "")
            if status in _SUCCESS_STATUSES:
                return last
            if status in _FAILURE_STATUSES:
                raise ApiCallError(
                    provider="tiktok",
                    method="POST",
                    url=f"{self._cfg.api_base.rstrip('/')}/v2/post/publish/status/fetch/",
                    status_code=None,
                    message=f"tiktok publish failed: {data}",
                    request={"publish_id": publish_id},
                    response_text=None,
                )
            time.sleep(interval_seconds)
        raise ApiCallError(
            provider="tiktok",
            method="POST",
            url=f"{self._cfg.api_base.rstrip('/')}/v2/post/publish/status/fetch/",
            status_code=None,
            message=f"tiktok publish status not terminal after polling: {last}",
            request={"publish_id": publish_id},
            response_text=None,
        )
