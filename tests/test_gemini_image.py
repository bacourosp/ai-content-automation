import base64

from xai_automation.services.gemini import GeminiClient, GeminiConfig


def test_generate_image_decodes_inline_data(monkeypatch) -> None:
    cfg = GeminiConfig(api_key="k", model="gemini-2.5-flash", timeout_seconds=5, image_model="gemini-2.5-flash-image")
    c = GeminiClient(cfg)
    raw = b"\x89PNG\r\n\x1a\n fake bytes"
    b64 = base64.b64encode(raw).decode("ascii")

    captured = {}

    def _fake_post_json(url, headers=None, payload=None, **kwargs):
        captured["url"] = url
        captured["payload"] = payload
        return {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": b64}}]}}]}

    monkeypatch.setattr(c._http, "post_json", _fake_post_json)
    out = c.generate_image(prompt="a vertical slide")
    assert out == raw
    assert "gemini-2.5-flash-image:generateContent" in captured["url"]
    assert captured["payload"]["generationConfig"]["responseModalities"] == ["IMAGE"]
