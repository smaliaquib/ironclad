from main import MAX_HISTORY_MESSAGES, SYSTEM_PROMPT, ChatMessage, build_messages


def test_build_messages_prepends_system_prompt():
    messages = build_messages([], "hi")
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}


def test_build_messages_appends_current_turn_last():
    messages = build_messages([], "what's the weather?")
    assert messages[-1] == {"role": "user", "content": "what's the weather?"}


def test_build_messages_includes_history_in_order():
    history = [
        ChatMessage(role="user", content="first"),
        ChatMessage(role="assistant", content="second"),
    ]
    messages = build_messages(history, "third")
    assert messages == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]


def test_build_messages_caps_history_length():
    history = [
        ChatMessage(role="user", content=f"turn {i}") for i in range(MAX_HISTORY_MESSAGES + 10)
    ]
    messages = build_messages(history, "latest")

    # system prompt + capped history + current turn
    assert len(messages) == 1 + MAX_HISTORY_MESSAGES + 1
    # the oldest turns are the ones dropped, not the newest
    assert messages[1] == {"role": "user", "content": "turn 10"}
    assert messages[-2] == {"role": "user", "content": f"turn {MAX_HISTORY_MESSAGES + 9}"}
