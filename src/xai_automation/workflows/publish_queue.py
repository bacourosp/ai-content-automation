from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from xai_automation.config.settings import Settings
from xai_automation.connectors.publish_facebook import FacebookConfig, FacebookPublisher
from xai_automation.connectors.publish_instagram import InstagramConfig, InstagramPublisher
from xai_automation.connectors.publish_tiktok import TikTokConfig, TikTokPublisher
from xai_automation.services.errors import ApiCallError
from xai_automation.services.retry import retry
from xai_automation.storage.repo import Repo


log = logging.getLogger("xai_automation.publish_queue")


def approve_job(*, repo: Repo, job_id: str) -> int:
    items = repo.list_publish_queue(statuses=["awaiting_approval"], limit=500)
    n = 0
    for it in items:
        if str(it.get("job_id")) != job_id:
            continue
        repo.update_publish_item(queue_id=str(it["id"]), status="queued", last_error="")
        n += 1
    return n


def process_queue(*, settings: Settings, repo: Repo, limit: int) -> int:
    items = repo.list_publish_queue(statuses=["queued"], limit=limit)
    if not items:
        return 0
    ok = 0
    for it in items:
        qid = str(it["id"])
        payload = json.loads(str(it.get("payload_json") or "{}"))
        job_id = str(payload.get("job_id") or "")
        asset_id = str(payload.get("video_asset_id") or "")
        try:
            _process_item(settings=settings, repo=repo, item=it)
            repo.update_publish_item(queue_id=qid, status="published", last_error="")
            ok += 1
        except Exception as e:
            if isinstance(e, ApiCallError):
                repo.log_api_error(job_id=job_id, asset_id=asset_id, err=e)
            repo.update_publish_item(queue_id=qid, attempts_inc=True, status="failed", last_error=str(e))
    return ok


def _process_item(*, settings: Settings, repo: Repo, item: dict[str, Any]) -> None:
    platform = str(item.get("platform") or "")
    payload = json.loads(str(item.get("payload_json") or "{}"))
    job_id = str(payload.get("job_id") or "")
    assets_dir = Path(str(payload.get("assets_dir") or ""))
    video_path = assets_dir / "video.mp4"

    if platform == "facebook":
        fb = FacebookPublisher(
            FacebookConfig(
                access_token=settings.meta_access_token,
                page_id=settings.facebook_page_id,
                api_version=settings.meta_graph_api_version,
            ),
            timeout_seconds=settings.timeout_seconds_publish,
        )
        post_long = str(payload["content_plan"]["facebook"]["post_long"] or "")
        cta = str(payload["content_plan"]["facebook"]["cta"] or "")
        msg = (post_long + "\n\n" + cta).strip()
        retry(lambda: fb.publish_text_post(message=msg), max_attempts=settings.retry_max, backoff_seconds=settings.retry_backoff_seconds)
        if video_path.exists():
            desc = str(payload["content_plan"]["facebook"]["video"]["script"] or "")
            retry(
                lambda: fb.publish_video(video_path=video_path, description=desc),
                max_attempts=settings.retry_max,
                backoff_seconds=settings.retry_backoff_seconds,
            )
        return

    if platform == "tiktok":
        if not video_path.exists():
            raise RuntimeError("tiktok requires video.mp4")
        tt = TikTokPublisher(TikTokConfig(access_token=settings.tiktok_access_token, api_base=settings.tiktok_api_base_url), timeout_seconds=settings.timeout_seconds_publish)
        title = str(payload["content_plan"]["tiktok"]["caption"] or payload.get("hook") or "AI update")
        init = retry(
            lambda: tt.init_video_publish(title=title, video_bytes=video_path.stat().st_size),
            max_attempts=settings.retry_max,
            backoff_seconds=settings.retry_backoff_seconds,
        )
        data = init.get("data") if isinstance(init, dict) else None
        if not isinstance(data, dict):
            raise RuntimeError("tiktok init missing data")
        upload_url = str(data.get("upload_url") or "")
        publish_id = str(data.get("publish_id") or "")
        if upload_url == "" or publish_id == "":
            raise RuntimeError("tiktok init missing upload_url/publish_id")
        retry(lambda: tt.upload_video(upload_url=upload_url, video_path=video_path), max_attempts=settings.retry_max, backoff_seconds=settings.retry_backoff_seconds)
        retry(lambda: tt.fetch_publish_status(publish_id=publish_id), max_attempts=settings.retry_max, backoff_seconds=settings.retry_backoff_seconds)
        return

    if platform == "instagram":
        if settings.public_base_url.strip() == "":
            raise RuntimeError("instagram requires PUBLIC_BASE_URL for video_url hosting")
        if not video_path.exists():
            raise RuntimeError("instagram requires video.mp4")
        pub = InstagramPublisher(
            InstagramConfig(
                access_token=settings.meta_access_token,
                ig_business_account_id=settings.instagram_business_account_id,
                api_version=settings.meta_graph_api_version,
            ),
            timeout_seconds=settings.timeout_seconds_publish,
        )
        rel = f"assets/{job_id}/video.mp4"
        video_url = settings.public_base_url.rstrip("/") + "/" + rel
        caption = str(payload["content_plan"]["instagram"]["caption"] or "")
        cta = str(payload["content_plan"]["instagram"]["cta"] or "")
        full_caption = (caption + "\n\n" + cta).strip()
        creation_id = retry(
            lambda: pub.create_reels_container(video_url=video_url, caption=full_caption),
            max_attempts=settings.retry_max,
            backoff_seconds=settings.retry_backoff_seconds,
        )
        for _ in range(20):
            st = pub.get_container_status(creation_id=creation_id)
            sc = str(st.get("status_code") or st.get("status") or "")
            if sc in {"FINISHED", "finished", "READY"}:
                break
            if sc in {"ERROR", "error", "EXPIRED"}:
                raise RuntimeError(f"instagram container failed: {st}")
            time.sleep(5)
        retry(
            lambda: pub.publish_container(creation_id=creation_id),
            max_attempts=settings.retry_max,
            backoff_seconds=settings.retry_backoff_seconds,
        )
        return

    raise RuntimeError(f"unknown platform: {platform}")
