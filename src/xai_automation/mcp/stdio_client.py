from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from xai_automation.mcp.http_client import McpError, McpTool

log = logging.getLogger("xai_automation.mcp.stdio")

PopenFactory = Callable[..., "subprocess.Popen[str]"]


class McpStdioClient:
    """MCP client over stdio (newline-delimited JSON-RPC 2.0).

    Spawns a local MCP server process (e.g. `npx -y pkg@x.y.z`) and talks to it
    on stdin/stdout. Mirrors `McpHttpClient` (`list_tools`, `call_tool`).

    `popen_factory` is injectable for hermetic tests.
    """

    def __init__(
        self,
        *,
        command: list[str],
        env: dict[str, str] | None = None,
        timeout_seconds: int = 120,
        popen_factory: PopenFactory | None = None,
    ) -> None:
        self._command = command
        self._env = env or {}
        self._timeout = timeout_seconds
        self._popen_factory = popen_factory or subprocess.Popen
        self._proc: subprocess.Popen[str] | None = None
        self._initialized = False
        self._q: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._reader: threading.Thread | None = None

    def _start(self) -> None:
        if self._proc is not None:
            return
        full_env = {**os.environ, **self._env}
        self._proc = self._popen_factory(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=full_env,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            s = line.strip()
            if not s:
                continue
            try:
                msg = json.loads(s)
            except Exception:
                continue  # ignore non-JSON log noise
            if isinstance(msg, dict):
                self._q.put(msg)

    def _write(self, payload: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise McpError("stdio process not started")
        proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        proc.stdin.flush()

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._write(payload)

    def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._start()
        rid = uuid.uuid4().hex
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        self._write(payload)

        end = time.monotonic() + self._timeout
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise McpError(f"stdio request timeout for {method}")
            try:
                msg = self._q.get(timeout=remaining)
            except queue.Empty as e:
                raise McpError(f"stdio request timeout for {method}") from e
            if msg.get("id") != rid:
                # response to a different request or a notification; ignore
                continue
            if "error" in msg:
                raise McpError(str(msg["error"]))
            if "result" not in msg:
                raise McpError("invalid mcp response (no result)")
            return msg["result"]

    def initialize(self) -> None:
        if self._initialized:
            return
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "xai-automation", "version": "0.1.0"},
                "capabilities": {},
            },
        )
        self._notify("notifications/initialized")
        self._initialized = True

    def list_tools(self) -> list[McpTool]:
        self.initialize()
        res = self._request("tools/list", {})
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
        return self._request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        self._proc = None
