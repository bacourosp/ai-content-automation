import json

from xai_automation.mcp.higgsfield import _build_tool_arguments, _extract_url_and_path
from xai_automation.mcp.http_client import McpTool


def _tool(schema: dict) -> McpTool:
    return McpTool(name="higgsfield.render", description="", input_schema=schema)


def test_build_args_prefers_configured_name_when_present() -> None:
    tool = _tool({"properties": {"video_spec": {}, "extra": {}}})
    assert _build_tool_arguments(tool=tool, video_spec={"a": 1}, preferred_arg="video_spec") == {"video_spec": {"a": 1}}


def test_build_args_single_property_schema() -> None:
    tool = _tool({"properties": {"spec": {}}})
    assert _build_tool_arguments(tool=tool, video_spec={"a": 1}, preferred_arg="video_spec") == {"spec": {"a": 1}}


def test_build_args_fallback_no_schema() -> None:
    tool = _tool({})
    assert _build_tool_arguments(tool=tool, video_spec={"a": 1}, preferred_arg="payload") == {"payload": {"a": 1}}


def test_extract_flat_dict() -> None:
    assert _extract_url_and_path({"video_url": "https://x/v.mp4"}) == ("https://x/v.mp4", "")
    assert _extract_url_and_path({"path": "/tmp/v.mp4"}) == ("", "/tmp/v.mp4")


def test_extract_structured_content() -> None:
    res = {"structuredContent": {"result_url": "https://x/v.mp4"}}
    assert _extract_url_and_path(res) == ("https://x/v.mp4", "")


def test_extract_content_text_url() -> None:
    res = {"content": [{"type": "text", "text": "https://cdn/v.mp4"}]}
    assert _extract_url_and_path(res) == ("https://cdn/v.mp4", "")


def test_extract_content_text_json() -> None:
    res = {"content": [{"type": "text", "text": json.dumps({"video_url": "https://cdn/v.mp4"})}]}
    assert _extract_url_and_path(res) == ("https://cdn/v.mp4", "")


def test_extract_content_resource() -> None:
    res = {"content": [{"type": "resource", "resource": {"uri": "https://cdn/v.mp4"}}]}
    assert _extract_url_and_path(res) == ("https://cdn/v.mp4", "")


def test_extract_nothing() -> None:
    assert _extract_url_and_path({"content": [{"type": "text", "text": "done"}]}) == ("", "")
