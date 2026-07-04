from main import sse_event


def test_sse_event_formats_token_event():
    formatted = sse_event("token", {"text": "hi"})
    assert formatted == 'event: token\ndata: {"text": "hi"}\n\n'


def test_sse_event_formats_done_event():
    formatted = sse_event("done", {})
    assert formatted == "event: done\ndata: {}\n\n"
