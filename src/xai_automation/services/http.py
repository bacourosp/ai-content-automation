from __future__ import annotations

import json
from typing import Any

import requests


class HttpClient:
    def __init__(self, *, timeout_seconds: int):
        self._timeout = timeout_seconds
        self._session = requests.Session()

    def get_json(self, url: str, *, headers: dict[str, str] | None = None, params: dict[str, str] | None = None) -> Any:
        r = self._session.get(url, headers=headers, params=params, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def post_json(self, url: str, *, headers: dict[str, str] | None = None, payload: Any) -> Any:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        r = self._session.post(url, headers=h, data=data, timeout=self._timeout)
        r.raise_for_status()
        if r.content:
            return r.json()
        return None

    def download_to_file(self, url: str, *, out_path, headers: dict[str, str] | None = None) -> None:
        r = self._session.get(url, headers=headers, timeout=self._timeout, stream=True)
        r.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
