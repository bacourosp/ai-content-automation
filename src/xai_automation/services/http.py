from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlencode

import requests

from xai_automation.services.errors import ApiCallError


log = logging.getLogger("xai_automation.http")

def _parse_sse_json(text: str) -> Any:
    raw = text or ""
    data_lines: list[str] = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s.startswith("data:"):
            continue
        v = s[5:].strip()
        if v and v != "[DONE]":
            data_lines.append(v)
    if not data_lines:
        raise ValueError("no data lines")
    return json.loads(data_lines[-1])


class HttpClient:
    def __init__(self, *, timeout_seconds: int):
        self._timeout = timeout_seconds
        self._session = requests.Session()

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        provider: str = "http",
    ) -> Any:
        req = {"headers": headers or {}, "params": params or {}}
        try:
            r = self._session.get(url, headers=headers, params=params, timeout=self._timeout)
            if r.status_code >= 400:
                raise ApiCallError(
                    provider=provider,
                    method="GET",
                    url=url,
                    status_code=int(r.status_code),
                    message=f"{r.status_code} {r.text[:500]}",
                    request=req,
                    response_text=r.text,
                )
            return r.json()
        except ApiCallError as e:
            if e.provider == "higgsfield" and e.is_quota:
                log.error("higgsfield quota/limit detected: %s", e.message)
            raise
        except Exception as e:
            raise ApiCallError(
                provider=provider,
                method="GET",
                url=url,
                status_code=None,
                message=str(e),
                request=req,
                response_text=None,
            ) from e

    def post_json(self, url: str, *, headers: dict[str, str] | None = None, payload: Any, provider: str = "http") -> Any:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        h = {"Content-Type": "application/json"}
        if provider == "higgsfield":
            h["Accept"] = "application/json, text/event-stream"
        if headers:
            h.update(headers)
        req = {"headers": h, "payload": payload}
        try:
            r = self._session.post(url, headers=h, data=data, timeout=self._timeout)
            if r.status_code >= 400:
                raise ApiCallError(
                    provider=provider,
                    method="POST",
                    url=url,
                    status_code=int(r.status_code),
                    message=f"{r.status_code} {r.text[:500]}",
                    request=req,
                    response_text=r.text,
                )
            if r.content:
                try:
                    return r.json()
                except Exception:
                    ct = str(r.headers.get("Content-Type") or "")
                    if "text/event-stream" in ct:
                        return _parse_sse_json(r.text)
                    raise
            return None
        except ApiCallError as e:
            if e.provider == "higgsfield" and e.is_quota:
                log.error("higgsfield quota/limit detected: %s", e.message)
            raise
        except Exception as e:
            raise ApiCallError(
                provider=provider,
                method="POST",
                url=url,
                status_code=None,
                message=str(e),
                request=req,
                response_text=None,
            ) from e

    def post_form(self, url: str, *, data: dict[str, str], headers: dict[str, str] | None = None, provider: str = "http") -> Any:
        body = urlencode(data).encode("utf-8")
        h = {"Content-Type": "application/x-www-form-urlencoded"}
        if headers:
            h.update(headers)
        req = {"headers": h, "form": data}
        try:
            r = self._session.post(url, headers=h, data=body, timeout=self._timeout)
            if r.status_code >= 400:
                raise ApiCallError(
                    provider=provider,
                    method="POST",
                    url=url,
                    status_code=int(r.status_code),
                    message=f"{r.status_code} {r.text[:500]}",
                    request=req,
                    response_text=r.text,
                )
            if r.content:
                return r.json()
            return None
        except ApiCallError:
            raise
        except Exception as e:
            raise ApiCallError(
                provider=provider,
                method="POST",
                url=url,
                status_code=None,
                message=str(e),
                request=req,
                response_text=None,
            ) from e

    def put_bytes(self, url: str, *, data: bytes, headers: dict[str, str] | None = None, provider: str = "http") -> Any:
        req = {"headers": headers or {}, "bytes": len(data)}
        try:
            r = self._session.put(url, headers=headers, data=data, timeout=self._timeout)
            if r.status_code >= 400:
                raise ApiCallError(
                    provider=provider,
                    method="PUT",
                    url=url,
                    status_code=int(r.status_code),
                    message=f"{r.status_code} {r.text[:500]}",
                    request=req,
                    response_text=r.text,
                )
            if r.content:
                try:
                    return r.json()
                except Exception:
                    return None
            return None
        except ApiCallError:
            raise
        except Exception as e:
            raise ApiCallError(
                provider=provider,
                method="PUT",
                url=url,
                status_code=None,
                message=str(e),
                request=req,
                response_text=None,
            ) from e

    def download_to_file(self, url: str, *, out_path, headers: dict[str, str] | None = None, provider: str = "http") -> None:
        req = {"headers": headers or {}}
        try:
            r = self._session.get(url, headers=headers, timeout=self._timeout, stream=True)
            if r.status_code >= 400:
                raise ApiCallError(
                    provider=provider,
                    method="GET",
                    url=url,
                    status_code=int(r.status_code),
                    message=f"{r.status_code} {r.text[:500]}",
                    request=req,
                    response_text=r.text,
                )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        except ApiCallError as e:
            if e.provider == "higgsfield" and e.is_quota:
                log.error("higgsfield quota/limit detected: %s", e.message)
            raise
        except Exception as e:
            raise ApiCallError(
                provider=provider,
                method="GET",
                url=url,
                status_code=None,
                message=str(e),
                request=req,
                response_text=None,
            ) from e
