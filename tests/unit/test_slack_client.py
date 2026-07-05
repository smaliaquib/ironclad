import json

import pytest

from tools import _slack_client


class FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture(autouse=True)
def reset_token_cache(monkeypatch):
    monkeypatch.setattr(_slack_client, "_cached_token", None)
    yield
    monkeypatch.setattr(_slack_client, "_cached_token", None)


def test_call_returns_payload_on_ok(monkeypatch):
    monkeypatch.setattr(_slack_client, "_get_token", lambda: "xoxb-fake")
    monkeypatch.setattr(
        _slack_client.urllib.request,
        "urlopen",
        lambda req, timeout=10: FakeHTTPResponse({"ok": True, "ts": "123.45"}),
    )

    result = _slack_client.call("chat.postMessage", {"channel": "C1", "text": "hi"})

    assert result == {"ok": True, "ts": "123.45"}


def test_call_raises_on_not_ok(monkeypatch):
    monkeypatch.setattr(_slack_client, "_get_token", lambda: "xoxb-fake")
    monkeypatch.setattr(
        _slack_client.urllib.request,
        "urlopen",
        lambda req, timeout=10: FakeHTTPResponse({"ok": False, "error": "channel_not_found"}),
    )

    with pytest.raises(RuntimeError, match="channel_not_found"):
        _slack_client.call("chat.postMessage", {"channel": "bogus", "text": "hi"})


def test_get_token_fetches_and_caches(monkeypatch):
    calls = []

    class FakeSSMClient:
        def get_parameter(self, Name, WithDecryption):
            calls.append((Name, WithDecryption))
            return {"Parameter": {"Value": "xoxb-real-token"}}

    monkeypatch.setattr(_slack_client.boto3, "client", lambda service: FakeSSMClient())

    first = _slack_client._get_token()
    second = _slack_client._get_token()

    assert first == "xoxb-real-token"
    assert second == "xoxb-real-token"
    assert len(calls) == 1
