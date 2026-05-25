from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from contextlib import suppress

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s]+")


def extract_public_url(line: str) -> str | None:
    for m in _URL_RE.finditer(line):
        url = m.group(0).rstrip(".,;)]\"'")
        if url.startswith(("http://localhost", "https://localhost", "http://127.", "https://127.")):
            continue
        return url
    return None


CreateSubprocessExec = Callable[..., Awaitable[asyncio.subprocess.Process]]


class TunnelManager:
    def __init__(
        self,
        *,
        local_port: int,
        cloudflared_path: str = "cloudflared",
        tunnel_token: str | None = None,
        public_url_hint: str | None = None,
        create_subprocess_exec: CreateSubprocessExec = asyncio.create_subprocess_exec,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.local_port = int(local_port)
        self.cloudflared_path = str(cloudflared_path)
        self.tunnel_token = tunnel_token.strip() if tunnel_token and tunnel_token.strip() else None
        self.public_url_hint = public_url_hint.strip() if public_url_hint and public_url_hint.strip() else None
        self._create_subprocess_exec = create_subprocess_exec
        self._sleep = sleep

        self.public_url: str | None = None
        self._public_url_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._runner_task: asyncio.Task[None] | None = None
        self._process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        if self._runner_task and not self._runner_task.done():
            return
        self._stop_event = asyncio.Event()
        self._runner_task = asyncio.create_task(self._run_forever())
        if self.public_url_hint:
            self.public_url = self.public_url_hint
            self._public_url_event.set()
            logger.info("=== TUNNEL ACTIVE === Public URL: `%s`", self.public_url_hint)

    async def stop(self) -> None:
        self._stop_event.set()
        proc = self._process
        if proc is not None:
            with suppress(Exception):
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                with suppress(Exception):
                    proc.kill()
        task = self._runner_task
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def wait_until_ready(self, *, timeout_seconds: float = 30) -> str:
        if self.public_url:
            return self.public_url
        await asyncio.wait_for(self._public_url_event.wait(), timeout=timeout_seconds)
        return self.public_url or ""

    async def _run_forever(self) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            self._public_url_event.clear()
            self.public_url = None if not self.public_url_hint else self.public_url_hint
            proc = await self._spawn()
            self._process = proc
            reader_task = asyncio.create_task(self._read_stdout(proc))
            try:
                await proc.wait()
            finally:
                reader_task.cancel()
                with suppress(asyncio.CancelledError):
                    await reader_task

            if self._stop_event.is_set():
                return

            await self._sleep(min(backoff, 30.0))
            backoff = min(backoff * 2.0, 30.0)

    async def _spawn(self) -> asyncio.subprocess.Process:
        if self.tunnel_token:
            cmd = [
                self.cloudflared_path,
                "tunnel",
                "run",
                "--token",
                self.tunnel_token,
                "--no-autoupdate",
            ]
        else:
            cmd = [
                self.cloudflared_path,
                "tunnel",
                "--url",
                f"http://localhost:{self.local_port}",
                "--no-autoupdate",
            ]
        return await self._create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

    async def _read_stdout(self, proc: asyncio.subprocess.Process) -> None:
        stdout = proc.stdout
        if stdout is None:
            return
        while True:
            raw = await stdout.readline()
            if not raw:
                return
            line = raw.decode("utf-8", errors="replace").strip()
            url = extract_public_url(line)
            if not url:
                continue
            if url == self.public_url:
                continue
            self.public_url = url
            self._public_url_event.set()
            logger.info("=== TUNNEL ACTIVE === Public URL: `%s`", url)

