import json

import pytest

from tools import _brave_client


class FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeHTTPError(Exception):
    def __init__(self, code, detail):
        self.code = code
        self._detail = detail.encode()

    def read(self):
        return self._detail


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    monkeypatch.setattr(_brave_client, "_cached_api_key", None)
    yield
    monkeypatch.setattr(_brave_client, "_cached_api_key", None)


def test_get_api_key_fetches_and_caches(monkeypatch):
    calls = []

    class FakeSSMClient:
        def get_parameter(self, Name, WithDecryption):
            calls.append(Name)
            return {"Parameter": {"Value": "BSA-real-key"}}

    monkeypatch.setattr(_brave_client.boto3, "client", lambda service: FakeSSMClient())

    first = _brave_client._get_api_key()
    second = _brave_client._get_api_key()

    assert first == "BSA-real-key"
    assert second == "BSA-real-key"
    assert len(calls) == 1


def test_call_returns_parsed_json(monkeypatch):
    monkeypatch.setattr(_brave_client, "_get_api_key", lambda: "key")
    monkeypatch.setattr(
        _brave_client.urllib.request,
        "urlopen",
        lambda request, timeout=15: FakeHTTPResponse({"web": {"results": []}}),
    )

    result = _brave_client.call("/res/v1/web/search", {"q": "test"})

    assert result == {"web": {"results": []}}


def test_call_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(_brave_client, "_get_api_key", lambda: "key")

    def raise_http_error(request, timeout=15):
        raise FakeHTTPError(429, "rate limited")

    monkeypatch.setattr(_brave_client.urllib.request, "urlopen", raise_http_error)
    monkeypatch.setattr(_brave_client.urllib.error, "HTTPError", FakeHTTPError)

    with pytest.raises(RuntimeError, match="429"):
        _brave_client.call("/res/v1/web/search", {"q": "test"})
