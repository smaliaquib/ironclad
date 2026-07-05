import base64

from tools import _gmail_client, gmail_read, gmail_reply, gmail_search, gmail_send


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_gmail_search_returns_results(monkeypatch):
    calls = []

    def fake_call(method, path, params=None, json_body=None):
        calls.append((method, path, params))
        if path == "/messages":
            return {"messages": [{"id": "m1", "threadId": "t1"}]}
        return {
            "id": "m1",
            "threadId": "t1",
            "snippet": "hello",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Hi"},
                    {"name": "From", "value": "a@b.com"},
                    {"name": "Date", "value": "today"},
                ]
            },
        }

    monkeypatch.setattr(_gmail_client, "call", fake_call)

    result = gmail_search.handler({"query": "is:unread"}, None)

    assert result == {
        "results": [
            {
                "id": "m1",
                "thread_id": "t1",
                "subject": "Hi",
                "sender": "a@b.com",
                "date": "today",
                "snippet": "hello",
            }
        ]
    }
    assert calls[0] == ("GET", "/messages", {"q": "is:unread", "maxResults": 10})


def test_gmail_search_rejects_missing_query():
    result = gmail_search.handler({}, None)
    assert "error" in result


def test_gmail_search_surfaces_api_error(monkeypatch):
    def raise_error(method, path, params=None, json_body=None):
        raise RuntimeError("Gmail API error (GET /messages): 401 unauthorized")

    monkeypatch.setattr(_gmail_client, "call", raise_error)

    result = gmail_search.handler({"query": "is:unread"}, None)
    assert "error" in result


def test_gmail_read_returns_plain_text_body(monkeypatch):
    monkeypatch.setattr(
        _gmail_client,
        "call",
        lambda method, path, params=None, json_body=None: {
            "id": "m1",
            "snippet": "hi there",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Hi"},
                    {"name": "From", "value": "a@b.com"},
                    {"name": "To", "value": "me@b.com"},
                    {"name": "Date", "value": "today"},
                ],
                "mimeType": "text/plain",
                "body": {"data": _b64("hi there, full body")},
            },
        },
    )

    result = gmail_read.handler({"message_id": "m1"}, None)

    assert result == {
        "subject": "Hi",
        "sender": "a@b.com",
        "to": "me@b.com",
        "date": "today",
        "snippet": "hi there",
        "body": "hi there, full body",
    }


def test_gmail_read_falls_back_to_nested_parts(monkeypatch):
    monkeypatch.setattr(
        _gmail_client,
        "call",
        lambda method, path, params=None, json_body=None: {
            "id": "m1",
            "snippet": "snip",
            "payload": {
                "headers": [],
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/html", "body": {"data": _b64("<p>html</p>")}},
                    {"mimeType": "text/plain", "body": {"data": _b64("plain body")}},
                ],
            },
        },
    )

    result = gmail_read.handler({"message_id": "m1"}, None)

    assert result["body"] == "plain body"


def test_gmail_read_rejects_missing_message_id():
    result = gmail_read.handler({}, None)
    assert "error" in result


def test_gmail_send_posts_raw_message(monkeypatch):
    calls = []

    def fake_call(method, path, params=None, json_body=None):
        calls.append((method, path, json_body))
        return {"id": "sent1", "threadId": "t1"}

    monkeypatch.setattr(_gmail_client, "call", fake_call)

    result = gmail_send.handler({"to": "a@b.com", "subject": "Hi", "body": "hello"}, None)

    assert result == {"id": "sent1", "thread_id": "t1"}
    method, path, json_body = calls[0]
    assert (method, path) == ("POST", "/messages/send")
    assert "raw" in json_body


def test_gmail_send_rejects_missing_fields():
    result = gmail_send.handler({"to": "a@b.com"}, None)
    assert "error" in result


def test_gmail_reply_uses_original_thread_and_headers(monkeypatch):
    calls = []

    def fake_call(method, path, params=None, json_body=None):
        calls.append((method, path, params, json_body))
        if method == "GET":
            return {
                "threadId": "t1",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Original"},
                        {"name": "From", "value": "a@b.com"},
                        {"name": "Message-Id", "value": "<msg1@mail>"},
                    ]
                },
            }
        return {"id": "reply1", "threadId": "t1"}

    monkeypatch.setattr(_gmail_client, "call", fake_call)

    result = gmail_reply.handler({"message_id": "m1", "body": "reply body"}, None)

    assert result == {"id": "reply1", "thread_id": "t1"}
    _, _, _, send_body = calls[1]
    assert send_body["threadId"] == "t1"


def test_gmail_reply_rejects_missing_body():
    result = gmail_reply.handler({"message_id": "m1"}, None)
    assert "error" in result
