from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


_SENSITIVE_KEY_RE = re.compile(r"(token|secret|api[_-]?key|authorization|cookie|password)", re.IGNORECASE)


def redact_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if _SENSITIVE_KEY_RE.search(str(k) or ""):
                out[k] = "***"
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [redact_secrets(x) for x in obj]
    if isinstance(obj, str):
        if len(obj) > 16 and any(p in obj.lower() for p in ["bearer ", "nvapi-", "sk-", "pk_", "secret"]):
            return "***"
        return obj
    return obj


def dumps_redacted(obj: Any) -> str:
    return json.dumps(redact_secrets(obj), ensure_ascii=False, separators=(",", ":"))


def is_quota_or_limit_error(*, status_code: int | None, message: str) -> bool:
    if status_code in {402, 403, 429}:
        return True
    m = (message or "").lower()
    for s in ["quota", "rate limit", "too many requests", "limit exceeded", "usage limit", "insufficient credits", "payment required"]:
        if s in m:
            return True
    return False


@dataclass(frozen=True)
class ApiCallError(RuntimeError):
    provider: str
    method: str
    url: str
    status_code: int | None
    message: str
    request: dict[str, Any] | None
    response_text: str | None

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self._format())

    def _format(self) -> str:
        sc = "" if self.status_code is None else f"{self.status_code} "
        return f"{self.provider} {self.method} {self.url} {sc}{self.message}".strip()

    def __str__(self) -> str:
        return self._format()

    @property
    def is_quota(self) -> bool:
        return is_quota_or_limit_error(status_code=self.status_code, message=self.message)
