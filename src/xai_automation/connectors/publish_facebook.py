from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from xai_automation.services.errors import ApiCallError


log = logging.getLogger("xai_automation.publish_facebook")


@dataclass(frozen=True)
class FacebookConfig:
    access_token: str
    page_id: str
    api_version: str = "v19.0"


class FacebookPublisher:
    def __init__(self, cfg: FacebookConfig, *, timeout_seconds: int):
        self._cfg = cfg
        self._timeout = timeout_seconds

    def publish_text_post(self, *, message: str) -> dict[str, Any]:
        if self._cfg.access_token.strip() == "" or self._cfg.page_id.strip() == "":
            raise ApiCallError(
                provider="facebook",
                method="POST",
                url="https://graph.facebook.com",
                status_code=None,
                message="missing facebook credentials",
                request=None,
                response_text=None,
            )
        url = f"https://graph.facebook.com/{self._cfg.api_version}/{self._cfg.page_id}/feed"
        data = {"message": message, "access_token": self._cfg.access_token}
        r = requests.post(url, data=data, timeout=self._timeout)
        if r.status_code >= 400:
            raise ApiCallError(
                provider="facebook",
                method="POST",
                url=url,
                status_code=int(r.status_code),
                message=f"{r.status_code} {r.text[:500]}",
                request={"data": data},
                response_text=r.text,
            )
        return r.json()

    def publish_video(self, *, video_path: Path, description: str) -> dict[str, Any]:
        if self._cfg.access_token.strip() == "" or self._cfg.page_id.strip() == "":
            raise ApiCallError(
                provider="facebook",
                method="POST",
                url="https://graph.facebook.com",
                status_code=None,
                message="missing facebook credentials",
                request=None,
                response_text=None,
            )
        if not video_path.exists():
            raise ApiCallError(
                provider="facebook",
                method="POST",
                url="https://graph.facebook.com",
                status_code=None,
                message="video file missing",
                request={"video_path": str(video_path)},
                response_text=None,
            )
        url = f"https://graph.facebook.com/{self._cfg.api_version}/{self._cfg.page_id}/videos"
        data = {"description": description, "access_token": self._cfg.access_token}
        with video_path.open("rb") as f:
            files = {"source": f}
            r = requests.post(url, data=data, files=files, timeout=self._timeout)
        if r.status_code >= 400:
            raise ApiCallError(
                provider="facebook",
                method="POST",
                url=url,
                status_code=int(r.status_code),
                message=f"{r.status_code} {r.text[:500]}",
                request={"data": data, "files": {"source": str(video_path)}},
                response_text=r.text,
            )
        return r.json()
