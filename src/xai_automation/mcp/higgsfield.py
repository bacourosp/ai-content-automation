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
    arg_name: str = "video_spec"


class HiggsfieldClient:
    def __init__(self, cfg: HiggsfieldConfig):
        self._cfg = cfg
        self._mcp = McpHttpClient(url=cfg.mcp_url, api_key=cfg.api_key, timeout_seconds=cfg.timeout_seconds)
        self._http = HttpClient(timeout_seconds=cfg.timeout_seconds)

    def resolve_tool(self) -> McpTool:
        tools = self._mcp.list_tools()
        if self._cfg.tool_name.strip():
            wanted = self._cfg.tool_name.strip()
            for t in tools:
                if t.name == wanted:
                    return t
            # Configured name not advertised; trust it with an empty schema.
            return McpTool(name=wanted, description="", input_schema={})
        picked = _pick_higgsfield_tool(tools)
        if picked is None:
            names = ",".join([t.name for t in tools][:30])
            raise HiggsfieldError(f"no suitable higgsfield tool found. tools={names}")
        for t in tools:
            if t.name == picked:
                return t
        return McpTool(name=picked, description="", input_schema={})

    def resolve_tool_name(self) -> str:
        return self.resolve_tool().name

    def render_video(self, *, video_spec: dict[str, Any]) -> dict[str, Any]:
        tool = self.resolve_tool()
        arguments = _build_tool_arguments(tool=tool, video_spec=video_spec, preferred_arg=self._cfg.arg_name)
        res = self._mcp.call_tool(name=tool.name, arguments=arguments)
        url, path = _extract_url_and_path(res)
        out: dict[str, Any] = {"raw": res}
        if url:
            out["video_url"] = url
        if path:
            out["video_path"] = path
        return out

    def download_if_url(self, *, maybe_url: str, out_path: Path) -> Path:
        u = (maybe_url or "").strip()
        if not (u.startswith("http://") or u.startswith("https://")):
            raise HiggsfieldError("not a url")
        self._http.download_to_file(u, out_path=out_path, provider="higgsfield")
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


def _build_tool_arguments(*, tool: McpTool, video_spec: dict[str, Any], preferred_arg: str) -> dict[str, Any]:
    """Map the video_spec onto the tool's expected argument key.

    Uses the advertised inputSchema when available so we adapt to the real
    Higgsfield tool; otherwise falls back to the configured arg name.
    """
    schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    pref = (preferred_arg or "video_spec").strip() or "video_spec"
    if props:
        if pref in props:
            return {pref: video_spec}
        if "video_spec" in props:
            return {"video_spec": video_spec}
        if len(props) == 1:
            only = next(iter(props.keys()))
            return {only: video_spec}
    return {pref: video_spec}


def _looks_like_url(s: str) -> bool:
    return s.startswith(("http://", "https://"))


def _scan_obj_for_media(obj: Any) -> tuple[str, str]:
    """Best-effort extraction of (url, path) from a dict of result fields."""
    url = ""
    path = ""
    if isinstance(obj, dict):
        url = str(obj.get("video_url") or obj.get("url") or obj.get("result_url") or "")
        path = str(obj.get("video_path") or obj.get("path") or "")
        if not url and isinstance(obj.get("uri"), str) and _looks_like_url(obj["uri"]):
            url = obj["uri"]
    return url, path


def _scan_content_item(item: Any) -> tuple[str, str]:
    if not isinstance(item, dict):
        return "", ""
    itype = str(item.get("type") or "")
    if itype == "resource":
        resource = item.get("resource") if isinstance(item.get("resource"), dict) else {}
        return _scan_obj_for_media(resource)
    if itype in ("json", "structured") and isinstance(item.get("json"), dict):
        return _scan_obj_for_media(item["json"])
    if itype == "text":
        text = str(item.get("text") or "").strip()
        if _looks_like_url(text):
            return text, ""
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return _scan_obj_for_media(parsed)
    return "", ""


def _extract_url_and_path(res: Any) -> tuple[str, str]:
    """Parse an MCP tools/call result for a rendered video URL or path.

    Handles the MCP-standard shape (``content[]`` items of type text/json/resource
    and ``structuredContent``) plus flat dicts returned by simpler servers.
    """
    if not isinstance(res, dict):
        return "", ""

    for candidate in (res, res.get("structuredContent")):
        url, path = _scan_obj_for_media(candidate)
        if url or path:
            return url, path

    content = res.get("content")
    if isinstance(content, list):
        for item in content:
            url, path = _scan_content_item(item)
            if url or path:
                return url, path
    return "", ""


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
