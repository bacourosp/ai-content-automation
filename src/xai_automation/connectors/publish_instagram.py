from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from xai_automation.services.errors import ApiCallError


log = logging.getLogger("xai_automation.publish_instagram")


@dataclass(frozen=True)
class InstagramConfig:
    access_token: str
    ig_business_account_id: str
    api_version: str = "v19.0"


class InstagramPublisher:
    def __init__(self, cfg: InstagramConfig, *, timeout_seconds: int):
        self._cfg = cfg
        self._timeout = timeout_seconds

    def create_reels_container(self, *, video_url: str, caption: str) -> str:
        if self._cfg.access_token.strip() == "" or self._cfg.ig_business_account_id.strip() == "":
            raise ApiCallError(
                provider="instagram",
                method="POST",
                url="https://graph.facebook.com",
                status_code=None,
                message="missing instagram credentials",
                request=None,
                response_text=None,
            )
        if not (video_url.startswith("https://") or video_url.startswith("http://")):
            raise ApiCallError(
                provider="instagram",
                method="POST",
                url="https://graph.facebook.com",
                status_code=None,
                message="video_url must be public http(s) url",
                request={"video_url": video_url},
                response_text=None,
            )
        url = f"https://graph.facebook.com/{self._cfg.api_version}/{self._cfg.ig_business_account_id}/media"
        data = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": self._cfg.access_token,
        }
        r = requests.post(url, data=data, timeout=self._timeout)
        if r.status_code >= 400:
            raise ApiCallError(
                provider="instagram",
                method="POST",
                url=url,
                status_code=int(r.status_code),
                message=f"{r.status_code} {r.text[:500]}",
                request={"data": data},
                response_text=r.text,
            )
        j = r.json()
        cid = j.get("id")
        if not isinstance(cid, str) or cid.strip() == "":
            raise ApiCallError(
                provider="instagram",
                method="POST",
                url=url,
                status_code=int(r.status_code),
                message="missing container id",
                request={"data": data},
                response_text=r.text,
            )
        return cid

    def publish_container(self, *, creation_id: str) -> dict[str, Any]:
        url = f"https://graph.facebook.com/{self._cfg.api_version}/{self._cfg.ig_business_account_id}/media_publish"
        data = {"creation_id": creation_id, "access_token": self._cfg.access_token}
        r = requests.post(url, data=data, timeout=self._timeout)
        if r.status_code >= 400:
            raise ApiCallError(
                provider="instagram",
                method="POST",
                url=url,
                status_code=int(r.status_code),
                message=f"{r.status_code} {r.text[:500]}",
                request={"data": data},
                response_text=r.text,
            )
        return r.json()

    def get_container_status(self, *, creation_id: str) -> dict[str, Any]:
        url = f"https://graph.facebook.com/{self._cfg.api_version}/{creation_id}"
        params = {"fields": "status_code,status", "access_token": self._cfg.access_token}
        r = requests.get(url, params=params, timeout=self._timeout)
        if r.status_code >= 400:
            raise ApiCallError(
                provider="instagram",
                method="GET",
                url=url,
                status_code=int(r.status_code),
                message=f"{r.status_code} {r.text[:500]}",
                request={"params": params},
                response_text=r.text,
            )
        return r.json()
