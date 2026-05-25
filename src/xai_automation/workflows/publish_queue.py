from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from xai_automation.config.env_writer import default_env_path, set_env_vars
from xai_automation.config.settings import Settings
from xai_automation.connectors.oauth_tiktok import TikTokOAuth, TikTokOAuthConfig
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
            _process_item(settings=settings, item=it)
            repo.update_publish_item(queue_id=qid, status="published", last_error="")
            ok += 1
        except Exception as e:
            if isinstance(e, ApiCallError):
                repo.log_api_error(job_id=job_id, asset_id=asset_id, err=e)
            repo.update_publish_item(queue_id=qid, attempts_inc=True, status="failed", last_error=str(e))
    return ok


def _process_item(*, settings: Settings, item: dict[str, Any]) -> None:
    platform = str(item.get("platform") or "")
    payload = json.loads(str(item.get("payload_json") or "{}"))
    job_id = str(payload.get("job_id") or "")
    assets_dir = Path(str(payload.get("assets_dir") or ""))
    video_path = assets_dir / "video.mp4"

    if platform == "facebook":
        _publish_facebook(settings=settings, payload=payload, video_path=video_path)
        return
    if platform == "tiktok":
        _publish_tiktok(settings=settings, payload=payload, video_path=video_path)
        return
    if platform == "instagram":
        _publish_instagram(settings=settings, payload=payload, job_id=job_id, video_path=video_path)
        return
    raise RuntimeError(f"unknown platform: {platform}")


def _publish_facebook(*, settings: Settings, payload: dict[str, Any], video_path: Path) -> None:
    fb = FacebookPublisher(
        FacebookConfig(
            access_token=settings.meta_access_token,
            page_id=settings.facebook_page_id,
            api_version=settings.meta_graph_api_version,
        ),
        timeout_seconds=settings.timeout_seconds_publish,
    )
    cp = payload["content_plan"]["facebook"]
    body = (str(cp.get("post_long") or "") + "\n\n" + str(cp.get("cta") or "")).strip()
    # Single publish: a video post already carries the copy, so no orphan text post.
    if video_path.exists():
        retry(
            lambda: fb.publish_video(video_path=video_path, description=body),
            max_attempts=settings.retry_max,
            backoff_seconds=settings.retry_backoff_seconds,
        )
    else:
        retry(
            lambda: fb.publish_text_post(message=body),
            max_attempts=settings.retry_max,
            backoff_seconds=settings.retry_backoff_seconds,
        )


def _refresh_tiktok_token(settings: Settings) -> str:
    oa = TikTokOAuth(
        TikTokOAuthConfig(
            client_key=settings.tiktok_client_key,
            client_secret=settings.tiktok_client_secret,
            api_base=settings.tiktok_api_base_url,
        )
    )
    tok = oa.refresh(refresh_token=settings.tiktok_refresh_token)
    access = str((tok or {}).get("access_token") or "")
    refresh = str((tok or {}).get("refresh_token") or settings.tiktok_refresh_token)
    if access:
        set_env_vars(default_env_path(), {"TIKTOK_ACCESS_TOKEN": access, "TIKTOK_REFRESH_TOKEN": refresh})
    return access


def _tiktok_flow(*, settings: Settings, access_token: str, title: str, video_path: Path) -> None:
    tt = TikTokPublisher(
        TikTokConfig(access_token=access_token, api_base=settings.tiktok_api_base_url),
        timeout_seconds=settings.timeout_seconds_publish,
    )
    init = retry(
        lambda: tt.init_video_publish(title=title, video_bytes=video_path.stat().st_size),
        max_attempts=settings.retry_max,
        backoff_seconds=settings.retry_backoff_seconds,
    )
    data = init["data"]
    retry(
        lambda: tt.upload_video(upload_url=str(data["upload_url"]), video_path=video_path),
        max_attempts=settings.retry_max,
        backoff_seconds=settings.retry_backoff_seconds,
    )
    tt.poll_until_done(publish_id=str(data["publish_id"]), max_attempts=24, interval_seconds=5)


def _publish_tiktok(*, settings: Settings, payload: dict[str, Any], video_path: Path) -> None:
    if not video_path.exists():
        raise RuntimeError("tiktok requires video.mp4")
    title = str(payload["content_plan"]["tiktok"].get("caption") or payload.get("hook") or "AI update")
    try:
        _tiktok_flow(settings=settings, access_token=settings.tiktok_access_token, title=title, video_path=video_path)
    except ApiCallError as e:
        can_refresh = e.status_code == 401 and settings.tiktok_refresh_token.strip() and settings.tiktok_client_key.strip()
        if not can_refresh:
            raise
        log.info("tiktok token expired; refreshing and retrying once")
        new_token = _refresh_tiktok_token(settings)
        if not new_token:
            raise
        _tiktok_flow(settings=settings, access_token=new_token, title=title, video_path=video_path)


def _publish_instagram(*, settings: Settings, payload: dict[str, Any], job_id: str, video_path: Path) -> None:
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
    cp = payload["content_plan"]["instagram"]
    full_caption = (str(cp.get("caption") or "") + "\n\n" + str(cp.get("cta") or "")).strip()
    creation_id = retry(
        lambda: pub.create_reels_container(video_url=video_url, caption=full_caption),
        max_attempts=settings.retry_max,
        backoff_seconds=settings.retry_backoff_seconds,
    )
    # Reels processing can take a while; poll up to ~3 min before giving up.
    for _ in range(40):
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
