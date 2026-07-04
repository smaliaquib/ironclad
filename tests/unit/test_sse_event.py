from main import sse_event


def test_sse_event_formats_token_event():
    formatted = sse_event("token", {"text": "hi"})
    assert formatted == 'event: token\ndata: {"text": "hi"}\n\n'


def test_sse_event_formats_done_event():
    formatted = sse_event("done", {})
    assert formatted == "event: done\ndata: {}\n\n"


def test_sse_event_formats_usage_event():
    formatted = sse_event("usage", {"input_tokens": 12, "output_tokens": 34})
    assert formatted == 'event: usage\ndata: {"input_tokens": 12, "output_tokens": 34}\n\n'
