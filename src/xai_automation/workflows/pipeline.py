from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any

from xai_automation.config.settings import Settings
from xai_automation.connectors.x_api import XApiClient, build_ai_query
from xai_automation.mcp.higgsfield import (
    HiggsfieldClient,
    HiggsfieldConfig,
    build_video_spec_from_storyboard,
    dump_video_spec,
)
from xai_automation.mcp.render import build_render_provider
from xai_automation.services.deepseek import DeepSeekClient, DeepSeekConfig, DeepSeekError, load_prompt
from xai_automation.services.filtering import is_candidate_ai_post
from xai_automation.services.errors import ApiCallError
from xai_automation.services.gemini import GeminiClient, GeminiConfig
from xai_automation.services.retry import retry
from xai_automation.storage.db import Database
from xai_automation.storage.repo import PostIn, Repo


log = logging.getLogger("xai_automation.pipeline")


def run_once(*, settings: Settings, db: Database) -> None:
    db.path.parent.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.assets_dir.mkdir(parents=True, exist_ok=True)

    repo = Repo(db)
    _ingest_and_process(settings=settings, repo=repo)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sources(settings: Settings) -> list[str]:
    raw = (settings.x_sources or "").strip()
    if raw == "":
        return ["search"]
    parts = [p.strip().lower() for p in raw.replace(";", ",").split(",") if p.strip()]
    if not parts:
        return ["search"]
    return parts


def _ingest_and_process(*, settings: Settings, repo: Repo) -> None:
    if settings.x_bearer_token.strip() == "":
        log.info("X_BEARER_TOKEN missing; skipping ingest")
        return

    x = XApiClient(bearer_token=settings.x_bearer_token, timeout_seconds=settings.timeout_seconds_x)

    collected: list[tuple[str, str, str, str, str, str, str]] = []
    user_id_cache: dict[str, str] = {}

    srcs = _sources(settings)
    max_results = min(100, max(10, settings.max_posts_per_tick))

    if "list" in srcs and settings.x_list_id.strip():
        k = f"x_list_since_id:{settings.x_list_id.strip()}"
        since_id = repo.get_kv(k)
        try:
            posts, newest = x.fetch_list_tweets(list_id=settings.x_list_id.strip(), since_id=since_id, max_results=max_results)
        except ApiCallError as e:
            repo.log_api_error(job_id="", asset_id="", err=e)
            return
        if newest:
            repo.set_kv(k, newest)
        for p in posts:
            collected.append(("x_list", p.id, p.author_handle, p.created_at, p.text, p.url, p.lang))

    if "accounts" in srcs and settings.x_accounts:
        for handle in settings.x_accounts[:50]:
            k = f"x_user_since_id:{handle.lstrip('@')}"
            since_id = repo.get_kv(k)
            try:
                posts, newest, uid = x.fetch_user_tweets(
                    handle=handle, since_id=since_id, max_results=min(50, max_results), user_id_cache=user_id_cache
                )
            except ApiCallError as e:
                repo.log_api_error(job_id="", asset_id="", err=e)
                continue
            repo.set_kv(f"x_user_id:{handle.lstrip('@')}", uid)
            if newest:
                repo.set_kv(k, newest)
            for p in posts:
                collected.append(("x_user", p.id, p.author_handle, p.created_at, p.text, p.url, p.lang))

    if "search" in srcs or ("timeline" in srcs and not ("list" in srcs or "accounts" in srcs)):
        q = build_ai_query(settings.x_include_keywords, settings.x_exclude_keywords, settings.x_language_hint)
        k = "x_search_since_id"
        since_id = repo.get_kv(k)
        try:
            posts, newest = x.fetch_recent_search(
                query=q, since_id=since_id, max_results=max_results, languages=settings.x_language_hint
            )
        except ApiCallError as e:
            repo.log_api_error(job_id="", asset_id="", err=e)
            return
        if newest:
            repo.set_kv(k, newest)
        for p in posts:
            collected.append(("x_search", p.id, p.author_handle, p.created_at, p.text, p.url, p.lang))

    if not collected:
        log.info("no posts collected")
        return

    seen_post_ids: set[str] = set()
    created_jobs: list[str] = []
    for source, pid, author, created_at, text, url, lang in collected:
        if pid in seen_post_ids:
            continue
        seen_post_ids.add(pid)
        if not is_candidate_ai_post(text=text, include_keywords=settings.x_include_keywords, exclude_keywords=settings.x_exclude_keywords):
            continue
        inserted = repo.upsert_post(
            PostIn(id=pid, source=source, author_handle=author or "", created_at=created_at, text=text, url=url, lang=lang or "")
        )
        if not inserted:
            continue
        jid = repo.create_job(post_id=pid, state="detected")
        created_jobs.append(jid)

    if not created_jobs:
        log.info("no new candidate jobs")
        return

    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "deepseek_score_v1.txt"
    prompt = load_prompt(prompt_path)
    ds: Any
    if settings.llm_provider == "gemini":
        ds = GeminiClient(
            GeminiConfig(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                timeout_seconds=settings.timeout_seconds_deepseek,
                max_output_tokens=settings.max_model_output_tokens,
                thinking_budget=settings.gemini_thinking_budget,
            )
        )
    else:
        ds = DeepSeekClient(
            DeepSeekConfig(
                api_key=settings.nvidia_api_key,
                base_url=settings.nvidia_api_base_url,
                model=settings.deepseek_model,
                timeout_seconds=settings.timeout_seconds_deepseek,
                max_output_tokens=settings.max_model_output_tokens,
            )
        )

    renderer, renderer_err = _build_renderer(settings)

    try:
        for jid in created_jobs[: settings.max_posts_per_tick]:
            _process_job(settings=settings, repo=repo, deepseek=ds, renderer=renderer, renderer_err=renderer_err, job_id=jid, prompt=prompt)
    finally:
        closer = getattr(renderer, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass

    if not settings.require_approval:
        from xai_automation.workflows.publish_queue import process_queue

        process_queue(settings=settings, repo=repo, limit=settings.max_posts_per_tick)


def _build_renderer(settings: Settings) -> tuple[Any, str]:
    """Build the configured render provider. Returns (client_or_None, error_msg).

    Higgsfield keeps its dedicated client (so the module-level `HiggsfieldClient`
    binding stays stub-able in tests). Other providers come from the registry.
    """
    if settings.render_provider == "higgsfield":
        return (
            HiggsfieldClient(
                HiggsfieldConfig(
                    mcp_url=settings.higgsfield_mcp_url,
                    api_key=settings.higgsfield_api_key,
                    timeout_seconds=settings.higgsfield_timeout_seconds,
                    tool_name=settings.higgsfield_tool_name,
                    arg_name=settings.higgsfield_arg_name,
                )
            ),
            "",
        )
    try:
        return build_render_provider(settings), ""
    except Exception as e:  # misconfigured alt provider: fail jobs cleanly, don't crash the tick
        return None, str(e)


def _render_provider_configured(settings: Settings) -> bool:
    p = settings.render_provider
    if p == "higgsfield":
        return bool(settings.higgsfield_mcp_url.strip() and settings.higgsfield_api_key.strip())
    if p == "glif":
        return bool(settings.glif_api_token.strip() and settings.glif_render_id.strip())
    if p == "remotion_media":
        return bool(settings.kie_api_key.strip())
    if p == "remotion_app":
        return bool(settings.remotion_app_mcp_url.strip())
    return bool(settings.render_mcp_url.strip())


def _render_cost_config(settings: Settings) -> tuple[float, float, int]:
    if settings.render_provider == "higgsfield":
        return (
            float(settings.higgsfield_cost_per_video_usd),
            float(settings.higgsfield_free_tier_monthly_usd),
            int(settings.higgsfield_free_tier_monthly_videos),
        )
    return (
        float(settings.render_cost_per_video_usd),
        float(settings.render_free_tier_monthly_usd),
        int(settings.render_free_tier_monthly_videos),
    )


def _process_job(*, settings: Settings, repo: Repo, deepseek: Any, renderer: Any, renderer_err: str, job_id: str, prompt: str) -> None:
    job = repo.get_job_post(job_id)
    if job is None:
        return
    repo.update_job(job_id=job_id, state="classified")

    post_text = str(job["text"] or "")
    if len(post_text) > settings.max_post_chars:
        post_text = post_text[: settings.max_post_chars]

    post_payload = {
        "post_text": post_text,
        "author_handle": str(job["author_handle"] or ""),
        "created_at": str(job["created_at"] or ""),
        "url": str(job["url"] or ""),
        "language_hint": ",".join(settings.x_language_hint),
    }

    def _call_ds() -> dict:
        repo.update_job(job_id=job_id, attempts_inc=True)
        return deepseek.score_post(prompt=prompt, post_payload=post_payload)

    try:
        score_json = retry(_call_ds, max_attempts=settings.retry_max, backoff_seconds=settings.retry_backoff_seconds)
    except ApiCallError as e:
        repo.log_api_error(job_id=job_id, asset_id="", err=e)
        repo.update_job(job_id=job_id, state="failed_deepseek", last_error=str(e))
        return
    except DeepSeekError as e:
        repo.update_job(job_id=job_id, state="failed_deepseek", last_error=str(e))
        return
    except Exception as e:
        repo.update_job(job_id=job_id, state="failed_deepseek", last_error=str(e))
        return

    score = int(score_json.get("topic_score", 0))
    repo.update_job(job_id=job_id, state="scored", topic_score=score, score_json=score_json, last_error="")

    if str(score_json.get("category") or "") == "spam" or score < 50:
        repo.update_job(job_id=job_id, state="dropped", last_error="")
        return

    cp = score_json["content_plan"]
    tiktok = cp["tiktok"]
    storyboard = tiktok["storyboard"]
    video_spec = build_video_spec_from_storyboard(
        hook=str(tiktok.get("hook") or ""),
        visual_style=str(score_json.get("visual_style") or ""),
        storyboard=storyboard,
        aspect_ratio="9:16",
    )

    spec_path = settings.assets_dir / job_id / "video_spec.json"
    dump_video_spec(spec_path, video_spec)

    repo.update_job(job_id=job_id, state="video_planned")

    provider = settings.render_provider
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    projected_cost, free_usd, free_videos = _render_cost_config(settings)
    if free_usd > 0 and projected_cost > 0:
        used = repo.get_monthly_cost_total(provider=provider, month_key=month_key)
        if used + projected_cost > free_usd:
            repo.update_job(job_id=job_id, state=f"blocked_{provider}_budget", last_error=f"{provider} monthly cost limit reached")
            return
    if free_videos > 0:
        used_units = repo.get_monthly_cost_units(provider=provider, month_key=month_key)
        if used_units + 1 > free_videos:
            repo.update_job(job_id=job_id, state=f"blocked_{provider}_budget", last_error=f"{provider} monthly video limit reached")
            return

    render_out: dict[str, Any] = {}
    if renderer is not None and _render_provider_configured(settings):
        try:
            render_out = retry(
                lambda: renderer.render_video(video_spec=video_spec),
                max_attempts=settings.retry_max,
                backoff_seconds=settings.retry_backoff_seconds,
            )
        except ApiCallError as e:
            repo.log_api_error(job_id=job_id, asset_id="", err=e)
            repo.update_job(job_id=job_id, state=f"failed_{provider}", last_error=str(e))
            render_out = {}
        except Exception as e:
            repo.update_job(job_id=job_id, state=f"failed_{provider}", last_error=str(e))
            render_out = {}
    else:
        repo.update_job(job_id=job_id, state=f"failed_{provider}", last_error=renderer_err or f"missing {provider} config")

    video_path: Path | None = None
    maybe_url = ""
    if isinstance(render_out, dict):
        maybe_url = str(render_out.get("video_url") or render_out.get("url") or render_out.get("result_url") or "")
        maybe_path = str(render_out.get("video_path") or render_out.get("path") or "")
        if maybe_path:
            p = Path(maybe_path)
            if p.exists():
                video_path = p
        elif maybe_url:
            video_path = settings.assets_dir / job_id / "video.mp4"
            try:
                renderer.download_if_url(maybe_url=maybe_url, out_path=video_path)
            except ApiCallError as e:
                repo.log_api_error(job_id=job_id, asset_id="", err=e)
                video_path = None
            except Exception:
                video_path = None

    video_asset_id = ""
    if video_path is not None and video_path.exists():
        video_asset_id = repo.add_asset(job_id=job_id, kind="video", platform="master", path=video_path)
        hosted_video_path = settings.output_dir / "assets" / job_id / "video.mp4"
        hosted_video_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(video_path, hosted_video_path)
        except Exception:
            pass
        repo.add_cost_event(
            provider=provider,
            job_id=job_id,
            asset_id=video_asset_id,
            month_key=month_key,
            cost_usd=float(projected_cost),
            units=1,
            details={"video_url": maybe_url, "kind": "video_render"},
        )
        repo.update_job(job_id=job_id, state="video_rendered", last_error="")
    else:
        repo.update_job(job_id=job_id, state="video_missing", last_error="")

    bundle_path = settings.output_dir / job_id / "content_bundle.json"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(json.dumps(score_json, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    repo.add_asset(job_id=job_id, kind="content_bundle", platform="all", path=bundle_path)

    _maybe_generate_carousel_images(settings=settings, repo=repo, job_id=job_id, score_json=score_json)

    approval_status = "awaiting_approval" if settings.require_approval else "queued"
    repo.enqueue_publish(
        job_id=job_id,
        platform="tiktok",
        payload=_build_publish_payload(score_json, job_id, settings, video_asset_id),
        status=approval_status,
    )
    repo.enqueue_publish(
        job_id=job_id,
        platform="instagram",
        payload=_build_publish_payload(score_json, job_id, settings, video_asset_id),
        status=approval_status,
    )
    repo.enqueue_publish(
        job_id=job_id,
        platform="facebook",
        payload=_build_publish_payload(score_json, job_id, settings, video_asset_id),
        status=approval_status,
    )

    repo.update_job(job_id=job_id, state="queued")


def _maybe_generate_carousel_images(*, settings: Settings, repo: Repo, job_id: str, score_json: dict) -> None:
    """Optional: render Instagram carousel slide images via the official Gemini image API.

    Off unless ENABLE_IMAGE_GEN=true and a Gemini key is present. Failures are
    swallowed so they never block the job. (Multi-image IG publishing = follow-up.)
    """
    if not settings.enable_image_gen or not settings.gemini_api_key.strip():
        return
    carousel = (score_json.get("content_plan", {}) or {}).get("instagram", {}).get("carousel", {}) or {}
    if not carousel.get("enabled"):
        return
    slides = carousel.get("slides") or []
    if not slides:
        return
    client = GeminiClient(
        GeminiConfig(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.timeout_seconds_deepseek,
            image_model=settings.gemini_image_model,
        )
    )
    style = str(score_json.get("visual_style") or "")
    for i, slide in enumerate(slides[:6]):
        if not isinstance(slide, dict):
            continue
        title = str(slide.get("title") or "")
        bullets = "; ".join(str(b) for b in (slide.get("bullets") or []))
        prompt = (
            f"Vertical 4:5 social media carousel slide. Visual style: {style}. "
            f"Headline: {title}. Key points: {bullets}. Clean, high-contrast, legible large text."
        )
        try:
            img = client.generate_image(prompt=prompt)
            out = settings.assets_dir / job_id / f"carousel_{i}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(img)
            repo.add_asset(job_id=job_id, kind="image", platform="instagram", path=out)
        except Exception as e:  # noqa: BLE001 - never block the job on image gen
            log.info("carousel image %d failed: %s", i, e)


def _build_publish_payload(score_json: dict, job_id: str, settings: Settings, video_asset_id: str) -> dict:
    return {
        "job_id": job_id,
        "video_asset_id": video_asset_id,
        "topic_score": int(score_json.get("topic_score", 0)),
        "category": str(score_json.get("category") or ""),
        "viral_angle": str(score_json.get("viral_angle") or ""),
        "hook": str(score_json.get("hook") or ""),
        "visual_style": str(score_json.get("visual_style") or ""),
        "content_plan": score_json.get("content_plan"),
        "assets_dir": str((settings.assets_dir / job_id).resolve()),
        "output_dir": str((settings.output_dir / job_id).resolve()),
        "public_base_url": settings.public_base_url,
    }
