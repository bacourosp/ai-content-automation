from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xai_automation.services.http import HttpClient


log = logging.getLogger("xai_automation.deepseek")


class DeepSeekError(RuntimeError):
    pass


VALID_CATEGORIES = frozenset(
    {
        "ai_news",
        "launches",
        "model_releases",
        "viral_ai_content",
        "research",
        "startups",
        "tools",
        "controversies",
        "spam",
    }
)

MAX_VIDEO_SECONDS = 600


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int
    max_output_tokens: int


class DeepSeekClient:
    def __init__(self, cfg: DeepSeekConfig):
        base = cfg.base_url.strip()
        if base == "":
            base = "https://integrate.api.nvidia.com/v1"
        self._cfg = cfg
        self._base = base.rstrip("/")
        self._http = HttpClient(timeout_seconds=cfg.timeout_seconds)

    def ping(self) -> dict[str, Any]:
        payload = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": "Devuelve únicamente JSON válido: {\"ok\":true}"},
                {"role": "user", "content": "ping"},
            ],
            "temperature": 0.0,
            "max_tokens": 16,
        }
        url = f"{self._base}/chat/completions"
        headers = {"Authorization": f"Bearer {self._cfg.api_key}"}
        j = self._http.post_json(url, headers=headers, payload=payload, provider="deepseek")
        try:
            txt = j["choices"][0]["message"]["content"]
        except Exception as e:
            raise DeepSeekError(f"invalid response: {e}") from e
        parsed = parse_json_object(txt)
        if parsed.get("ok") is not True:
            raise DeepSeekError("ping returned non-ok")
        return parsed

    def score_post(self, *, prompt: str, post_payload: dict[str, str]) -> dict[str, Any]:
        content = _build_user_content(post_payload)
        payload = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": content},
            ],
            "temperature": 0.2,
            "max_tokens": int(self._cfg.max_output_tokens),
        }
        url = f"{self._base}/chat/completions"
        headers = {"Authorization": f"Bearer {self._cfg.api_key}"}
        j = self._http.post_json(url, headers=headers, payload=payload, provider="deepseek")
        try:
            txt = j["choices"][0]["message"]["content"]
        except Exception as e:
            raise DeepSeekError(f"invalid response: {e}") from e
        return parse_strict_json(txt)


def load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _build_user_content(post_payload: dict[str, str]) -> str:
    keys = ["post_text", "author_handle", "created_at", "url", "language_hint"]
    parts: list[str] = []
    for k in keys:
        v = (post_payload.get(k) or "").strip()
        parts.append(f"{k}: {v}")
    return "\n".join(parts)


def parse_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw == "":
        raise DeepSeekError("empty model output")
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise DeepSeekError("no json object found")
    obj = raw[start : end + 1]
    try:
        parsed = json.loads(obj)
    except Exception as e:
        raise DeepSeekError(f"json parse failed: {e}") from e
    if not isinstance(parsed, dict):
        raise DeepSeekError("root is not object")
    return parsed


def parse_strict_json(text: str) -> dict[str, Any]:
    parsed = parse_json_object(text)
    _validate_score_schema(parsed)
    return parsed


def _require_str(d: dict[str, Any], k: str) -> str:
    v = d.get(k)
    if not isinstance(v, str):
        raise DeepSeekError(f"{k} must be string")
    return v


def _require_int(d: dict[str, Any], k: str) -> int:
    v = d.get(k)
    if not isinstance(v, int):
        raise DeepSeekError(f"{k} must be int")
    return v


def _require_list(d: dict[str, Any], k: str) -> list[Any]:
    v = d.get(k)
    if not isinstance(v, list):
        raise DeepSeekError(f"{k} must be list")
    return v


def _require_obj(d: dict[str, Any], k: str) -> dict[str, Any]:
    v = d.get(k)
    if not isinstance(v, dict):
        raise DeepSeekError(f"{k} must be object")
    return v


def _require_seconds(d: dict[str, Any], k: str) -> int:
    v = _require_int(d, k)
    if v < 0 or v > MAX_VIDEO_SECONDS:
        raise DeepSeekError(f"{k} out of range (0..{MAX_VIDEO_SECONDS})")
    return v


def _validate_carousel_slides(slides: Any, *, path: str) -> None:
    if not isinstance(slides, list):
        raise DeepSeekError(f"{path} must be list")
    for i, slide in enumerate(slides[:20]):
        if not isinstance(slide, dict):
            raise DeepSeekError(f"{path}[{i}] must be object")
        if not isinstance(slide.get("title"), str):
            raise DeepSeekError(f"{path}[{i}].title must be string")
        if not isinstance(slide.get("bullets"), list):
            raise DeepSeekError(f"{path}[{i}].bullets must be list")
        if not isinstance(slide.get("footer"), str):
            raise DeepSeekError(f"{path}[{i}].footer must be string")


def _validate_storyboard(sb: Any, *, path: str) -> None:
    if not isinstance(sb, list) or not sb:
        raise DeepSeekError(f"{path} must be non-empty list")
    for i, item in enumerate(sb[:40]):
        if not isinstance(item, dict):
            raise DeepSeekError(f"{path}[{i}] must be object")
        for k in ["t", "duration", "on_screen_text", "voiceover", "visual", "broll"]:
            if k in {"t", "duration"}:
                if not isinstance(item.get(k), int):
                    raise DeepSeekError(f"{path}[{i}].{k} must be int")
            else:
                if not isinstance(item.get(k), str):
                    raise DeepSeekError(f"{path}[{i}].{k} must be string")


def _validate_score_schema(root: dict[str, Any]) -> None:
    score = _require_int(root, "topic_score")
    if score < 0 or score > 100:
        raise DeepSeekError("topic_score out of range")
    category = _require_str(root, "category")
    if category not in VALID_CATEGORIES:
        raise DeepSeekError(f"category must be one of {sorted(VALID_CATEGORIES)}")
    _require_str(root, "viral_angle")
    _require_str(root, "hook")
    _require_str(root, "audience")
    _require_str(root, "visual_style")

    cp = _require_obj(root, "content_plan")

    tt = _require_obj(cp, "tiktok")
    _require_seconds(tt, "seconds")
    _require_str(tt, "hook")
    _require_str(tt, "script")
    _validate_storyboard(tt.get("storyboard"), path="content_plan.tiktok.storyboard")
    _require_str(tt, "caption")
    _require_list(tt, "hashtags")
    _require_list(tt, "shot_list")
    _require_list(tt, "broll_suggestions")

    ig = _require_obj(cp, "instagram")
    reel = _require_obj(ig, "reel")
    _require_seconds(reel, "seconds")
    _require_str(reel, "hook")
    _require_str(reel, "script")
    _validate_storyboard(reel.get("storyboard"), path="content_plan.instagram.reel.storyboard")
    _require_str(ig, "caption")
    _require_str(ig, "cta")
    _require_list(ig, "hashtags")
    carousel = _require_obj(ig, "carousel")
    if not isinstance(carousel.get("enabled"), bool):
        raise DeepSeekError("content_plan.instagram.carousel.enabled must be bool")
    _validate_carousel_slides(carousel.get("slides"), path="content_plan.instagram.carousel.slides")

    fb = _require_obj(cp, "facebook")
    _require_str(fb, "post_long")
    _require_str(fb, "cta")
    _require_list(fb, "hashtags")
    fbv = _require_obj(fb, "video")
    _require_seconds(fbv, "seconds")
    _require_str(fbv, "hook")
    _require_str(fbv, "script")
    _validate_storyboard(fbv.get("storyboard"), path="content_plan.facebook.video.storyboard")
