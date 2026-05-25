from xai_automation.services.gemini import GeminiClient, GeminiConfig


def test_score_post_uses_json_mime_and_token_budget(monkeypatch) -> None:
    cfg = GeminiConfig(api_key="k", model="gemini-2.5-flash", timeout_seconds=5, max_output_tokens=4000, temperature=0.3)
    c = GeminiClient(cfg)
    captured = {}

    valid = {
        "topic_score": 60,
        "category": "tools",
        "viral_angle": "v",
        "hook": "h",
        "audience": "a",
        "visual_style": "s",
        "content_plan": {
            "tiktok": {"seconds": 20, "hook": "h", "script": "s", "storyboard": [{"t": 0, "duration": 5, "on_screen_text": "x", "voiceover": "y", "visual": "z", "broll": "b"}], "caption": "c", "hashtags": ["#a"], "shot_list": ["s"], "broll_suggestions": ["b"]},
            "instagram": {"reel": {"seconds": 20, "hook": "h", "script": "s", "storyboard": [{"t": 0, "duration": 5, "on_screen_text": "x", "voiceover": "y", "visual": "z", "broll": "b"}]}, "caption": "c", "cta": "cta", "hashtags": ["#a"], "carousel": {"enabled": False, "slides": []}},
            "facebook": {"post_long": "p", "cta": "cta", "hashtags": ["#a"], "video": {"seconds": 20, "hook": "h", "script": "s", "storyboard": [{"t": 0, "duration": 5, "on_screen_text": "x", "voiceover": "y", "visual": "z", "broll": "b"}]}},
        },
    }

    import json

    def _fake_post_json(url, headers=None, payload=None, **kwargs):
        captured["payload"] = payload
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(valid)}]}}]}

    monkeypatch.setattr(c._http, "post_json", _fake_post_json)
    out = c.score_post(prompt="P", post_payload={"post_text": "hello"})
    assert out["topic_score"] == 60
    gc = captured["payload"]["generationConfig"]
    assert gc["responseMimeType"] == "application/json"
    assert gc["maxOutputTokens"] == 4000
    # thinking must be disabled so the token budget goes to the JSON, not reasoning
    assert gc["thinkingConfig"]["thinkingBudget"] == 0
