from xai_automation.mcp.http_client import McpHttpClient


def test_mcp_list_tools_parses_tools(monkeypatch) -> None:
    c = McpHttpClient(url="http://localhost", api_key="k", timeout_seconds=5)

    calls = []

    def _fake_post_json(url, headers, payload, **kwargs):
        calls.append(payload["method"])
        if payload["method"] == "initialize":
            return {"jsonrpc": "2.0", "id": payload["id"], "result": {}}
        if payload["method"] == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {"tools": [{"name": "higgsfield.render", "description": "", "inputSchema": {"type": "object"}}]},
            }
        return {"jsonrpc": "2.0", "id": payload["id"], "result": {}}

    monkeypatch.setattr(c._http, "post_json", _fake_post_json)
    tools = c.list_tools()
    assert calls[0] == "initialize"
    assert tools[0].name == "higgsfield.render"
