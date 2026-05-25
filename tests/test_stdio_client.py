from __future__ import annotations

import sys

from xai_automation.mcp.stdio_client import McpStdioClient

# A tiny hermetic MCP server (no network) used to exercise real stdio framing.
_SERVER = r'''
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    mid = msg.get("id")
    method = msg.get("method")
    if mid is None:
        continue  # notification
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05"}
    elif method == "tools/list":
        result = {"tools": [{"name": "render_video", "description": "d", "inputSchema": {"properties": {"prompt": {}}}}]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": "https://cdn/v.mp4"}]}
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {"message": "unknown"}}) + "\n")
        sys.stdout.flush()
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\n")
    sys.stdout.flush()
'''


def test_stdio_client_list_and_call(tmp_path) -> None:
    script = tmp_path / "srv.py"
    script.write_text(_SERVER, encoding="utf-8")
    client = McpStdioClient(command=[sys.executable, str(script)], timeout_seconds=10)
    try:
        tools = client.list_tools()
        assert [t.name for t in tools] == ["render_video"]
        res = client.call_tool(name="render_video", arguments={"prompt": "hi"})
        assert res["content"][0]["text"] == "https://cdn/v.mp4"
    finally:
        client.close()
