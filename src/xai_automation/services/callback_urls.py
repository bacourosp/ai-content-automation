from __future__ import annotations


def normalize_base_url(base_url: str) -> str:
    u = (base_url or "").strip()
    while u.endswith("/"):
        u = u[:-1]
    return u


def compute_callback_urls(base_url: str) -> dict[str, str]:
    base = normalize_base_url(base_url)
    return {
        "PUBLIC_BASE_URL": base,
        "TIKTOK_REDIRECT_URI": base + "/callback/tiktok",
        "META_REDIRECT_URI": base + "/callback/meta",
        "ASSETS_VIDEO_URL_TEMPLATE": base + "/assets/<JOB_ID>/video.mp4",
    }

