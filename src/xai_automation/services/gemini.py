from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any

from xai_automation.services.deepseek import DeepSeekError, parse_json_object, parse_strict_json
from xai_automation.services.http import HttpClient


log = logging.getLogger("xai_automation.gemini")


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str
    model: str
    timeout_seconds: int
    max_output_tokens: int = 4000
    temperature: float = 0.3
    image_model: str = "gemini-2.5-flash-image"
    thinking_budget: int = 0  # 0 disables "thinking" so the token budget goes to JSON output


class GeminiClient:
    def __init__(self, cfg: GeminiConfig):
        self._cfg = cfg
        self._http = HttpClient(timeout_seconds=cfg.timeout_seconds)
        self._base = "https://generativelanguage.googleapis.com/v1beta"

    def ping(self) -> dict[str, Any]:
        url = f"{self._base}/models/{self._cfg.model}:generateContent?key={self._cfg.api_key}"
        payload = {"contents": [{"role": "user", "parts": [{"text": "Devuelve únicamente JSON válido: {\"ok\":true}"}]}]}
        j = self._http.post_json(url, payload=payload, provider="gemini")
        txt = _extract_text(j)
        parsed = parse_json_object(txt)
        if parsed.get("ok") is not True:
            raise DeepSeekError("ping returned non-ok")
        return parsed

    def score_post(self, *, prompt: str, post_payload: dict[str, str]) -> dict[str, Any]:
        url = f"{self._base}/models/{self._cfg.model}:generateContent?key={self._cfg.api_key}"
        content = _build_user_content(post_payload)
        sys_prompt = prompt.strip()
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": sys_prompt + "\n\n" + content}]},
            ],
            "generationConfig": {
                "temperature": float(self._cfg.temperature),
                "maxOutputTokens": int(self._cfg.max_output_tokens),
                "responseMimeType": "application/json",
                "thinkingConfig": {"thinkingBudget": int(self._cfg.thinking_budget)},
            },
        }
        j = self._http.post_json(url, payload=payload, provider="gemini")
        txt = _extract_text(j)
        return parse_strict_json(txt)

    def generate_image(self, *, prompt: str) -> bytes:
        """Generate an image with the official Gemini image model. Returns raw bytes."""
        url = f"{self._base}/models/{self._cfg.image_model}:generateContent?key={self._cfg.api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        j = self._http.post_json(url, payload=payload, provider="gemini")
        return base64.b64decode(_extract_inline_image(j))


def _extract_text(j: Any) -> str:
    try:
        cands = j["candidates"]
        parts = cands[0]["content"]["parts"]
        return str(parts[0]["text"])
    except Exception as e:
        raise DeepSeekError(f"invalid response: {e}") from e


def _extract_inline_image(j: Any) -> str:
    """Return the base64 image data from a generateContent image response."""
    try:
        parts = j["candidates"][0]["content"]["parts"]
    except Exception as e:
        raise DeepSeekError(f"invalid image response: {e}") from e
    for part in parts:
        if not isinstance(part, dict):
            continue
        blob = part.get("inlineData") or part.get("inline_data")
        if isinstance(blob, dict) and blob.get("data"):
            return str(blob["data"])
    raise DeepSeekError("image response had no inlineData")


def _build_user_content(post_payload: dict[str, str]) -> str:
    keys = ["post_text", "author_handle", "created_at", "url", "language_hint"]
    parts: list[str] = []
    for k in keys:
        v = (post_payload.get(k) or "").strip()
        parts.append(f"{k}: {v}")
    return "\n".join(parts)
