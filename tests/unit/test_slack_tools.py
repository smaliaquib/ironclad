from tools import _slack_client, slack_list_channels, slack_post_message, slack_read_history


def test_slack_post_message_returns_ok(monkeypatch):
    monkeypatch.setattr(
        _slack_client, "call", lambda method, params: {"channel": params["channel"], "ts": "1.1"}
    )

    result = slack_post_message.handler({"channel": "C1", "text": "hi"}, None)

    assert result == {"ok": True, "channel": "C1", "ts": "1.1"}


def test_slack_post_message_rejects_missing_field():
    result = slack_post_message.handler({"channel": "C1"}, None)
    assert "error" in result


def test_slack_post_message_surfaces_slack_api_error(monkeypatch):
    def raise_error(method, params):
        raise RuntimeError("Slack API error (chat.postMessage): channel_not_found")

    monkeypatch.setattr(_slack_client, "call", raise_error)

    result = slack_post_message.handler({"channel": "bogus", "text": "hi"}, None)

    assert "error" in result
    assert "channel_not_found" in result["error"]


def test_slack_read_history_returns_messages(monkeypatch):
    monkeypatch.setattr(
        _slack_client,
        "call",
        lambda method, params: {
            "messages": [{"user": "U1", "text": "hello", "ts": "1.1"}, {"text": "bot msg"}]
        },
    )

    result = slack_read_history.handler({"channel": "C1"}, None)

    assert result == {
        "messages": [
            {"user": "U1", "text": "hello", "ts": "1.1"},
            {"user": "", "text": "bot msg", "ts": ""},
        ]
    }


def test_slack_read_history_rejects_missing_channel():
    result = slack_read_history.handler({}, None)
    assert "error" in result


def test_slack_read_history_rejects_limit_out_of_range():
    result = slack_read_history.handler({"channel": "C1", "limit": 500}, None)
    assert "error" in result


def test_slack_list_channels_returns_channels(monkeypatch):
    monkeypatch.setattr(
        _slack_client,
        "call",
        lambda method, params: {
            "channels": [{"id": "C1", "name": "general"}, {"id": "C2", "name": "random"}]
        },
    )

    result = slack_list_channels.handler({}, None)

    assert result == {"channels": [{"id": "C1", "name": "general"}, {"id": "C2", "name": "random"}]}


def test_slack_list_channels_ignores_none_event(monkeypatch):
    monkeypatch.setattr(_slack_client, "call", lambda method, params: {"channels": []})

    result = slack_list_channels.handler(None, None)

    assert result == {"channels": []}
