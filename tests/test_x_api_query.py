from xai_automation.connectors.x_api import build_ai_query


def test_build_ai_query_contains_filters() -> None:
    q = build_ai_query(["ai", "openai"], ["crypto"], ["en"])
    assert "ai" in q
    assert "-crypto" in q
    assert "-is:retweet" in q
    assert "lang:en" in q

