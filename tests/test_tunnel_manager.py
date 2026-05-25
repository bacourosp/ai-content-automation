from __future__ import annotations

import asyncio


class _FakeStdout:
    def __init__(self, lines: list[str]):
        self._lines = [x if x.endswith("\n") else (x + "\n") for x in lines]
        self._i = 0

    async def readline(self) -> bytes:
        if self._i >= len(self._lines):
            await asyncio.sleep(0)
            return b""
        line = self._lines[self._i]
        self._i += 1
        await asyncio.sleep(0)
        return line.encode("utf-8")


class _FakeProcess:
    def __init__(self, *, stdout_lines: list[str], returncode: int = 0, already_exited: bool = False):
        self.stdout = _FakeStdout(stdout_lines)
        self.returncode = returncode
        self._wait_event = asyncio.Event()
        if already_exited:
            self._wait_event.set()

    async def wait(self) -> int:
        await self._wait_event.wait()
        return int(self.returncode)

    def terminate(self) -> None:
        self._wait_event.set()

    def kill(self) -> None:
        self._wait_event.set()


def test_extract_public_url_parses_trycloudflare() -> None:
    from xai_automation.services.tunnel_manager import extract_public_url

    line = "INF Published URL: https://abc123.trycloudflare.com"
    assert extract_public_url(line) == "https://abc123.trycloudflare.com"


def test_extract_public_url_ignores_localhost() -> None:
    from xai_automation.services.tunnel_manager import extract_public_url

    line = "http://localhost:8080"
    assert extract_public_url(line) is None


def test_tunnel_manager_ephemeral_builds_expected_command() -> None:
    from xai_automation.services.tunnel_manager import TunnelManager

    calls: list[tuple[str, ...]] = []

    async def _create_subprocess_exec(*cmd, **kwargs):
        calls.append(tuple(str(x) for x in cmd))
        return _FakeProcess(stdout_lines=["https://z.trycloudflare.com"], already_exited=False)

    async def _run():
        mgr = TunnelManager(
            local_port=8080,
            cloudflared_path="cloudflared",
            tunnel_token=None,
            create_subprocess_exec=_create_subprocess_exec,
        )
        await mgr.start()
        url = await mgr.wait_until_ready(timeout_seconds=1)
        assert url == "https://z.trycloudflare.com"
        await mgr.stop()

    asyncio.run(_run())
    assert calls
    assert calls[0][:2] == ("cloudflared", "tunnel")
    assert "--url" in calls[0]


def test_tunnel_manager_fixed_token_builds_expected_command() -> None:
    from xai_automation.services.tunnel_manager import TunnelManager

    calls: list[tuple[str, ...]] = []

    async def _create_subprocess_exec(*cmd, **kwargs):
        calls.append(tuple(str(x) for x in cmd))
        return _FakeProcess(stdout_lines=["https://webhook.example.com"], already_exited=False)

    async def _run():
        mgr = TunnelManager(
            local_port=8080,
            cloudflared_path="cloudflared",
            tunnel_token="tok_123",
            create_subprocess_exec=_create_subprocess_exec,
        )
        await mgr.start()
        await mgr.wait_until_ready(timeout_seconds=1)
        await mgr.stop()

    asyncio.run(_run())
    assert calls
    assert calls[0][:3] == ("cloudflared", "tunnel", "run")
    assert "--token" in calls[0]


def test_tunnel_manager_restarts_when_process_exits() -> None:
    from xai_automation.services.tunnel_manager import TunnelManager

    created = 0
    sleeps: list[float] = []

    async def _sleep(seconds: float) -> None:
        sleeps.append(float(seconds))
        await asyncio.sleep(0)

    async def _create_subprocess_exec(*cmd, **kwargs):
        nonlocal created
        created += 1
        if created == 1:
            return _FakeProcess(stdout_lines=["https://a.trycloudflare.com"], already_exited=True)
        return _FakeProcess(stdout_lines=["https://b.trycloudflare.com"], already_exited=False)

    async def _run():
        mgr = TunnelManager(
            local_port=8080,
            cloudflared_path="cloudflared",
            tunnel_token=None,
            create_subprocess_exec=_create_subprocess_exec,
            sleep=_sleep,
        )
        await mgr.start()
        url = await mgr.wait_until_ready(timeout_seconds=1)
        assert url in {"https://a.trycloudflare.com", "https://b.trycloudflare.com"}
        await asyncio.sleep(0)
        assert created >= 2
        assert sleeps and sleeps[0] <= 30
        await mgr.stop()

    asyncio.run(_run())

