from __future__ import annotations

import re


_URL_RE = re.compile(r"https?://\S+")


def is_candidate_ai_post(
    *,
    text: str,
    include_keywords: list[str],
    exclude_keywords: list[str],
    max_urls: int = 2,
) -> bool:
    t = (text or "").strip()
    if t == "":
        return False
    low = t.lower()
    for k in exclude_keywords:
        kk = k.strip().lower()
        if kk and kk in low:
            return False
    if include_keywords:
        ok = False
        for k in include_keywords:
            kk = k.strip().lower()
            if kk and kk in low:
                ok = True
                break
        if not ok:
            return False
    urls = _URL_RE.findall(t)
    if len(urls) > max_urls:
        return False
    return True
