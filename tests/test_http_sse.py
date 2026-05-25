from xai_automation.services.http import HttpClient


def test_http_client_parses_higgsfield_sse_json(monkeypatch) -> None:
    c = HttpClient(timeout_seconds=5)

    class _Resp:
        status_code = 200
        headers = {"Content-Type": "text/event-stream"}
        text = 'event: message\ndata: {"jsonrpc":"2.0","id":"1","result":{"ok":true}}\n\n'
        content = b"x"

        def json(self):
            raise ValueError("not json")

    def _fake_post(url, headers, data, timeout):
        return _Resp()

    monkeypatch.setattr(c._session, "post", _fake_post)
    out = c.post_json("http://localhost", payload={"x": 1}, provider="higgsfield")
    assert out["result"]["ok"] is True

