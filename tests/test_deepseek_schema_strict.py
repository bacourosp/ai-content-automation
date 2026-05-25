import copy
import json

import pytest

from xai_automation.services.deepseek import DeepSeekError, parse_strict_json

_SB = [{"t": 0, "duration": 5, "on_screen_text": "A", "voiceover": "B", "visual": "C", "broll": "D"}]


def _valid() -> dict:
    return {
        "topic_score": 80,
        "category": "ai_news",
        "viral_angle": "fast update",
        "hook": "New model drop",
        "audience": "builders",
        "visual_style": "clean tech",
        "content_plan": {
            "tiktok": {
                "seconds": 25,
                "hook": "Hook",
                "script": "Script",
                "storyboard": _SB,
                "caption": "Cap",
                "hashtags": ["#ai"],
                "shot_list": ["Shot 1"],
                "broll_suggestions": ["Broll 1"],
            },
            "instagram": {
                "reel": {"seconds": 25, "hook": "Hook", "script": "Script", "storyboard": _SB},
                "caption": "Cap",
                "cta": "CTA",
                "hashtags": ["#ai"],
                "carousel": {"enabled": False, "slides": []},
            },
            "facebook": {
                "post_long": "Post",
                "cta": "CTA",
                "hashtags": ["#ai"],
                "video": {"seconds": 25, "hook": "Hook", "script": "Script", "storyboard": _SB},
            },
        },
    }


def test_valid_passes() -> None:
    assert parse_strict_json(json.dumps(_valid()))["topic_score"] == 80


def test_invalid_category_rejected() -> None:
    bad = _valid()
    bad["category"] = "totally_made_up"
    with pytest.raises(DeepSeekError):
        parse_strict_json(json.dumps(bad))


def test_seconds_out_of_range_rejected() -> None:
    bad = _valid()
    bad["content_plan"]["tiktok"]["seconds"] = 99999
    with pytest.raises(DeepSeekError):
        parse_strict_json(json.dumps(bad))


def test_carousel_slides_structure_validated() -> None:
    good = _valid()
    good["content_plan"]["instagram"]["carousel"] = {
        "enabled": True,
        "slides": [{"title": "T", "bullets": ["a", "b"], "footer": "f"}],
    }
    assert parse_strict_json(json.dumps(good))["topic_score"] == 80

    bad = copy.deepcopy(good)
    bad["content_plan"]["instagram"]["carousel"]["slides"] = [{"title": "T", "footer": "f"}]  # missing bullets
    with pytest.raises(DeepSeekError):
        parse_strict_json(json.dumps(bad))
