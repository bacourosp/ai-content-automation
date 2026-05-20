from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from xai_automation.services.http import HttpClient


log = logging.getLogger("xai_automation.mcp")


class McpError(RuntimeError):
    pass


@dataclass(frozen=True)
class McpTool:
    name: str
    description: str
    input_schema: dict[str, Any]


class McpHttpClient:
    def __init__(self, *, url: str, api_key: str, timeout_seconds: int):
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._http = HttpClient(timeout_seconds=timeout_seconds)
        self._initialized = False

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._api_key.strip():
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        rid = uuid.uuid4().hex
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        j = self._http.post_json(self._url, headers=self._headers(), payload=payload)
        if isinstance(j, dict) and "error" in j:
            raise McpError(str(j["error"]))
        if not isinstance(j, dict) or "result" not in j:
            raise McpError("invalid mcp response")
        return j["result"]

    def initialize(self) -> None:
        if self._initialized:
            return
        self._rpc(
            "initialize",
            {
                "clientInfo": {"name": "xai-automation", "version": "0.1.0"},
                "capabilities": {},
            },
        )
        self._initialized = True

    def list_tools(self) -> list[McpTool]:
        self.initialize()
        res = self._rpc("tools/list", {})
        tools = res.get("tools") if isinstance(res, dict) else None
        if not isinstance(tools, list):
            raise McpError("tools/list missing tools")
        out: list[McpTool] = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            name = str(t.get("name") or "")
            if name == "":
                continue
            out.append(
                McpTool(
                    name=name,
                    description=str(t.get("description") or ""),
                    input_schema=t.get("inputSchema") if isinstance(t.get("inputSchema"), dict) else {},
                )
            )
        return out

    def call_tool(self, *, name: str, arguments: dict[str, Any]) -> Any:
        self.initialize()
        res = self._rpc("tools/call", {"name": name, "arguments": arguments})
        return res
