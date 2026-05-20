from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xai_automation.mcp.http_client import McpHttpClient, McpTool
from xai_automation.services.http import HttpClient


log = logging.getLogger("xai_automation.higgsfield")


class HiggsfieldError(RuntimeError):
    pass


@dataclass(frozen=True)
class HiggsfieldConfig:
    mcp_url: str
    api_key: str
    timeout_seconds: int
    tool_name: str


class HiggsfieldClient:
    def __init__(self, cfg: HiggsfieldConfig):
        self._cfg = cfg
        self._mcp = McpHttpClient(url=cfg.mcp_url, api_key=cfg.api_key, timeout_seconds=cfg.timeout_seconds)
        self._http = HttpClient(timeout_seconds=cfg.timeout_seconds)

    def resolve_tool_name(self) -> str:
        if self._cfg.tool_name.strip():
            return self._cfg.tool_name.strip()
        tools = self._mcp.list_tools()
        picked = _pick_higgsfield_tool(tools)
        if picked is None:
            names = ",".join([t.name for t in tools][:30])
            raise HiggsfieldError(f"no suitable higgsfield tool found. tools={names}")
        return picked

    def render_video(self, *, video_spec: dict[str, Any]) -> dict[str, Any]:
        tool = self.resolve_tool_name()
        res = self._mcp.call_tool(name=tool, arguments={"video_spec": video_spec})
        if not isinstance(res, dict):
            return {"raw": res}
        return res

    def download_if_url(self, *, maybe_url: str, out_path: Path) -> Path:
        u = (maybe_url or "").strip()
        if not (u.startswith("http://") or u.startswith("https://")):
            raise HiggsfieldError("not a url")
        self._http.download_to_file(u, out_path=out_path)
        return out_path


def _pick_higgsfield_tool(tools: list[McpTool]) -> str | None:
    candidates: list[str] = []
    for t in tools:
        n = t.name.lower()
        if "higgsfield" in n and ("video" in n or "render" in n or "generate" in n):
            candidates.append(t.name)
    if candidates:
        return sorted(candidates)[0]
    for t in tools:
        n = t.name.lower()
        if "video" in n and ("render" in n or "generate" in n):
            return t.name
    return None


def build_video_spec_from_storyboard(
    *,
    hook: str,
    visual_style: str,
    storyboard: list[dict[str, Any]],
    aspect_ratio: str,
) -> dict[str, Any]:
    scenes: list[dict[str, Any]] = []
    for s in storyboard[:20]:
        scenes.append(
            {
                "t": int(s.get("t", 0)),
                "duration": int(s.get("duration", 0)),
                "on_screen_text": str(s.get("on_screen_text", "")),
                "voiceover": str(s.get("voiceover", "")),
                "visual": str(s.get("visual", "")),
                "broll": str(s.get("broll", "")),
            }
        )
    return {
        "version": "1",
        "aspect_ratio": aspect_ratio,
        "style": visual_style,
        "hook": hook,
        "scenes": scenes,
    }


def dump_video_spec(path: Path, spec: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
