from xai_automation.services.callback_urls import compute_callback_urls, normalize_base_url


def test_normalize_base_url_strips_trailing_slash() -> None:
    assert normalize_base_url("https://example.com/") == "https://example.com"


def test_compute_callback_urls_builds_expected_paths() -> None:
    u = compute_callback_urls("https://example.com")
    assert u["PUBLIC_BASE_URL"] == "https://example.com"
    assert u["TIKTOK_REDIRECT_URI"] == "https://example.com/callback/tiktok"
    assert u["META_REDIRECT_URI"] == "https://example.com/callback/meta"
    assert u["ASSETS_VIDEO_URL_TEMPLATE"] == "https://example.com/assets/<JOB_ID>/video.mp4"

