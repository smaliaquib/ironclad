import json

import pytest

from tools import _gmail_client


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
def reset_caches(monkeypatch):
    monkeypatch.setattr(_gmail_client, "_cached_credentials", None)
    monkeypatch.setattr(_gmail_client, "_cached_access_token", None)
    monkeypatch.setattr(_gmail_client, "_access_token_expires_at", 0.0)
    yield
    monkeypatch.setattr(_gmail_client, "_cached_credentials", None)
    monkeypatch.setattr(_gmail_client, "_cached_access_token", None)
    monkeypatch.setattr(_gmail_client, "_access_token_expires_at", 0.0)


def test_get_credentials_fetches_and_caches(monkeypatch):
    calls = []

    class FakeSSMClient:
        def get_parameter(self, Name, WithDecryption):
            calls.append(Name)
            return {
                "Parameter": {
                    "Value": json.dumps(
                        {"client_id": "id", "client_secret": "secret", "refresh_token": "rt"}
                    )
                }
            }

    monkeypatch.setattr(_gmail_client.boto3, "client", lambda service: FakeSSMClient())

    first = _gmail_client._get_credentials()
    second = _gmail_client._get_credentials()

    assert first == {"client_id": "id", "client_secret": "secret", "refresh_token": "rt"}
    assert first is second
    assert len(calls) == 1


def test_get_access_token_exchanges_and_caches_until_expiry(monkeypatch):
    monkeypatch.setattr(
        _gmail_client,
        "_get_credentials",
        lambda: {"client_id": "id", "client_secret": "secret", "refresh_token": "rt"},
    )
    exchange_calls = []

    def fake_urlopen(request, timeout=10):
        exchange_calls.append(request)
        return FakeHTTPResponse({"access_token": "tok-1", "expires_in": 3600})

    monkeypatch.setattr(_gmail_client.urllib.request, "urlopen", fake_urlopen)

    first = _gmail_client._get_access_token()
    second = _gmail_client._get_access_token()

    assert first == "tok-1"
    assert second == "tok-1"
    assert len(exchange_calls) == 1


def test_get_access_token_refreshes_after_expiry(monkeypatch):
    monkeypatch.setattr(
        _gmail_client,
        "_get_credentials",
        lambda: {"client_id": "id", "client_secret": "secret", "refresh_token": "rt"},
    )
    monkeypatch.setattr(
        _gmail_client.urllib.request,
        "urlopen",
        lambda request, timeout=10: FakeHTTPResponse({"access_token": "tok-2", "expires_in": 3600}),
    )
    monkeypatch.setattr(_gmail_client, "_cached_access_token", "tok-old")
    monkeypatch.setattr(_gmail_client, "_access_token_expires_at", 0.0)  # already expired

    token = _gmail_client._get_access_token()

    assert token == "tok-2"


def test_call_returns_parsed_json(monkeypatch):
    monkeypatch.setattr(_gmail_client, "_get_access_token", lambda: "tok")
    monkeypatch.setattr(
        _gmail_client.urllib.request,
        "urlopen",
        lambda request, timeout=15: FakeHTTPResponse({"id": "m1"}),
    )

    result = _gmail_client.call("GET", "/messages/m1")

    assert result == {"id": "m1"}


def test_call_raises_runtime_error_on_http_error(monkeypatch):
    monkeypatch.setattr(_gmail_client, "_get_access_token", lambda: "tok")

    def raise_http_error(request, timeout=15):
        raise FakeHTTPError(404, "not found")

    monkeypatch.setattr(_gmail_client.urllib.request, "urlopen", raise_http_error)
    monkeypatch.setattr(_gmail_client.urllib.error, "HTTPError", FakeHTTPError)

    with pytest.raises(RuntimeError, match="404"):
        _gmail_client.call("GET", "/messages/bogus")


def test_build_raw_message_is_valid_base64url():
    raw = _gmail_client.build_raw_message("a@b.com", "Hi", "hello there")

    decoded = _gmail_client.decode_body_data(raw)
    assert "hello there" in decoded
    assert "Hi" in decoded


def test_decode_body_data_handles_missing_padding():
    import base64

    original = "hello world"
    encoded = base64.urlsafe_b64encode(original.encode()).decode().rstrip("=")

    assert _gmail_client.decode_body_data(encoded) == original
