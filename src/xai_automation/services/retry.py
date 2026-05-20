from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


def retry(
    fn: Callable[[], T],
    *,
    max_attempts: int,
    backoff_seconds: int,
    is_retryable: Callable[[Exception], bool] | None = None,
) -> T:
    attempt = 0
    last_exc: Exception | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if is_retryable is not None and not is_retryable(e):
                raise
            if attempt >= max_attempts:
                raise
            time.sleep(backoff_seconds * attempt)
    raise last_exc if last_exc is not None else RuntimeError("retry: exhausted")
