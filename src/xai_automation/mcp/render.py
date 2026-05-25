from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from xai_automation.mcp.higgsfield import _build_tool_arguments, _extract_url_and_path
from xai_automation.mcp.http_client import McpError, McpHttpClient, McpTool
from xai_automation.mcp.stdio_client import McpStdioClient
from xai_automation.services.http import HttpClient

log = logging.getLogger("xai_automation.mcp.render")


class McpTransport(Protocol):
    def list_tools(self) -> list[McpTool]: ...
    def call_tool(self, *, name: str, arguments: dict[str, Any]) -> Any: ...


class RenderError(RuntimeError):
    pass


def build_prompt_from_video_spec(video_spec: dict[str, Any]) -> str:
    """Flatten the canonical storyboard spec into one generation prompt.

    Used by prompt-based providers (glif, remotion-media) that take a text prompt
    rather than a structured storyboard.
    """
    parts: list[str] = []
    hook = str(video_spec.get("hook") or "").strip()
    style = str(video_spec.get("style") or "").strip()
    ar = str(video_spec.get("aspect_ratio") or "9:16").strip()
    if hook:
        parts.append(f"Hook: {hook}")
    if style:
        parts.append(f"Style: {style}")
    parts.append(f"Aspect ratio: {ar} vertical short-form video.")
    scenes = video_spec.get("scenes") if isinstance(video_spec.get("scenes"), list) else []
    for i, s in enumerate(scenes[:12], start=1):
        if not isinstance(s, dict):
            continue
        seg = []
        if s.get("on_screen_text"):
            seg.append(f"text '{s['on_screen_text']}'")
        if s.get("visual"):
            seg.append(f"visual {s['visual']}")
        if s.get("voiceover"):
            seg.append(f"vo '{s['voiceover']}'")
        if seg:
            parts.append(f"Scene {i} ({int(s.get('duration', 0))}s): " + "; ".join(seg))
    return "\n".join(parts)


def _pick_render_tool(tools: list[McpTool]) -> str | None:
    for t in tools:
        n = t.name.lower()
        if "video" in n and ("render" in n or "generate" in n or "create" in n):
            return t.name
    for t in tools:
        n = t.name.lower()
        if "render" in n or "generate" in n or "video" in n:
            return t.name
    return tools[0].name if tools else None


@dataclass(frozen=True)
class RenderProviderConfig:
    provider: str
    transport: str  # "http" | "stdio"
    input_kind: str = "spec"  # "spec" | "prompt"
    tool_name: str = ""
    arg_name: str = "video_spec"
    prompt_as_list: bool = False
    extra_args: dict[str, Any] = field(default_factory=dict)
    # http transport
    url: str = ""
    api_key: str = ""
    # stdio transport
    command: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 120


class McpRenderClient:
    """Generic MCP render client over either HTTP or stdio transport."""

    def __init__(self, cfg: RenderProviderConfig):
        self._cfg = cfg
        if cfg.transport == "stdio":
            self._mcp: McpTransport = McpStdioClient(command=cfg.command, env=cfg.env, timeout_seconds=cfg.timeout_seconds)
        else:
            self._mcp = McpHttpClient(url=cfg.url, api_key=cfg.api_key, timeout_seconds=cfg.timeout_seconds, provider=cfg.provider)
        self._http = HttpClient(timeout_seconds=cfg.timeout_seconds)

    def resolve_tool(self) -> McpTool:
        tools = self._mcp.list_tools()
        if self._cfg.tool_name.strip():
            wanted = self._cfg.tool_name.strip()
            for t in tools:
                if t.name == wanted:
                    return t
            return McpTool(name=wanted, description="", input_schema={})
        picked = _pick_render_tool(tools)
        if picked is None:
            raise RenderError(f"{self._cfg.provider}: no suitable tool found")
        for t in tools:
            if t.name == picked:
                return t
        return McpTool(name=picked, description="", input_schema={})

    def _arguments(self, tool: McpTool, video_spec: dict[str, Any]) -> dict[str, Any]:
        if self._cfg.input_kind == "prompt":
            prompt = build_prompt_from_video_spec(video_spec)
            value: Any = [prompt] if self._cfg.prompt_as_list else prompt
            return {**self._cfg.extra_args, self._cfg.arg_name: value}
        args = _build_tool_arguments(tool=tool, video_spec=video_spec, preferred_arg=self._cfg.arg_name)
        return {**self._cfg.extra_args, **args}

    def render_video(self, *, video_spec: dict[str, Any]) -> dict[str, Any]:
        tool = self.resolve_tool()
        res = self._mcp.call_tool(name=tool.name, arguments=self._arguments(tool, video_spec))
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
            raise RenderError("not a url")
        self._http.download_to_file(u, out_path=out_path, provider=self._cfg.provider)
        return out_path

    def close(self) -> None:
        closer = getattr(self._mcp, "close", None)
        if callable(closer):
            closer()


def _is_local_url(url: str) -> bool:
    u = url.lower()
    return any(h in u for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "192.168.", "10.", "host.docker.internal"))


def build_render_provider(settings: Any) -> McpRenderClient:
    """Construct the configured render provider (non-higgsfield).

    Higgsfield keeps using its dedicated client in the pipeline so existing
    tests/stubs are unaffected.
    """
    provider = settings.render_provider
    timeout = int(settings.higgsfield_timeout_seconds)

    if provider == "glif":
        if not settings.glif_render_id.strip():
            raise RenderError("glif requires GLIF_RENDER_ID (a fixed glif id to run)")
        return McpRenderClient(
            RenderProviderConfig(
                provider="glif",
                transport="stdio",
                input_kind="prompt",
                tool_name=settings.glif_tool_name or "run_glif",
                arg_name="inputs",
                prompt_as_list=True,
                extra_args={"id": settings.glif_render_id},
                command=_split_command(settings.glif_mcp_command),
                env={"GLIF_API_TOKEN": settings.glif_api_token},
                timeout_seconds=timeout,
            )
        )

    if provider == "remotion_media":
        return McpRenderClient(
            RenderProviderConfig(
                provider="remotion_media",
                transport="stdio",
                input_kind="prompt",
                tool_name=settings.render_tool_name,
                arg_name=settings.render_arg_name or "prompt",
                command=_split_command(settings.remotion_media_mcp_command),
                env={"KIE_API_KEY": settings.kie_api_key},
                timeout_seconds=timeout,
            )
        )

    if provider == "remotion_app":
        url = settings.remotion_app_mcp_url.strip()
        if not url:
            raise RenderError("remotion_app requires REMOTION_APP_MCP_URL")
        if not _is_local_url(url):
            raise RenderError(
                "remotion_app must be self-hosted (local/private URL) due to arbitrary-code-execution risk; "
                f"refusing non-local URL: {url}"
            )
        return McpRenderClient(
            RenderProviderConfig(
                provider="remotion_app",
                transport="http",
                input_kind="prompt",
                tool_name=settings.render_tool_name,
                arg_name=settings.render_arg_name or "prompt",
                url=url,
                timeout_seconds=timeout,
            )
        )

    # Generic HTTP MCP provider ("mcp"): point at any MCP-over-HTTP render server.
    url = settings.render_mcp_url.strip()
    if not url:
        raise RenderError(f"render provider '{provider}' requires RENDER_MCP_URL")
    return McpRenderClient(
        RenderProviderConfig(
            provider=provider,
            transport="http",
            input_kind=settings.render_input_kind or "spec",
            tool_name=settings.render_tool_name,
            arg_name=settings.render_arg_name or "video_spec",
            url=url,
            api_key=settings.render_api_key,
            timeout_seconds=timeout,
        )
    )


def _split_command(cmd: str) -> list[str]:
    import shlex

    return shlex.split(cmd) if cmd.strip() else []
