from __future__ import annotations

import pytest

from xai_automation.config.settings import load_settings
from xai_automation.mcp.http_client import McpTool
from xai_automation.mcp.render import (
    McpRenderClient,
    RenderError,
    RenderProviderConfig,
    build_prompt_from_video_spec,
    build_render_provider,
)

_SPEC = {
    "version": "1",
    "aspect_ratio": "9:16",
    "style": "tech minimal",
    "hook": "New model drop",
    "scenes": [
        {"t": 0, "duration": 5, "on_screen_text": "Big news", "voiceover": "vo1", "visual": "screen", "broll": "b"},
    ],
}


def test_build_prompt_from_video_spec() -> None:
    p = build_prompt_from_video_spec(_SPEC)
    assert "Hook: New model drop" in p
    assert "tech minimal" in p
    assert "Scene 1" in p


def test_glif_requires_render_id(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_PROVIDER", "glif")
    monkeypatch.setenv("GLIF_API_TOKEN", "t")
    monkeypatch.delenv("GLIF_RENDER_ID", raising=False)
    with pytest.raises(RenderError):
        build_render_provider(load_settings())


def test_remotion_app_rejects_public_url(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_PROVIDER", "remotion_app")
    monkeypatch.setenv("REMOTION_APP_MCP_URL", "https://evil.example.com/mcp")
    with pytest.raises(RenderError):
        build_render_provider(load_settings())


def test_remotion_app_accepts_localhost(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_PROVIDER", "remotion_app")
    monkeypatch.setenv("REMOTION_APP_MCP_URL", "http://localhost:3000/mcp")
    client = build_render_provider(load_settings())
    assert isinstance(client, McpRenderClient)


def test_generic_mcp_requires_url(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_PROVIDER", "mcp")
    monkeypatch.delenv("RENDER_MCP_URL", raising=False)
    with pytest.raises(RenderError):
        build_render_provider(load_settings())


class _FakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def list_tools(self):
        return [McpTool(name="run_glif", description="", input_schema={"properties": {"id": {}, "inputs": {}}})]

    def call_tool(self, *, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        return {"content": [{"type": "text", "text": "https://cdn/out.mp4"}]}


def test_prompt_provider_builds_list_args_and_extracts_url() -> None:
    cfg = RenderProviderConfig(
        provider="glif",
        transport="http",
        input_kind="prompt",
        tool_name="run_glif",
        arg_name="inputs",
        prompt_as_list=True,
        extra_args={"id": "GLIF123"},
        url="http://x",
    )
    client = McpRenderClient(cfg)
    fake = _FakeTransport()
    client._mcp = fake  # inject transport (no network)
    out = client.render_video(video_spec=_SPEC)
    assert out["video_url"] == "https://cdn/out.mp4"
    args = fake.calls[0]["arguments"]
    assert args["id"] == "GLIF123"
    assert isinstance(args["inputs"], list) and len(args["inputs"]) == 1
