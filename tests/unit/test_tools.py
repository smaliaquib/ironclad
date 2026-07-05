from tools import add_numbers, echo, get_time


def test_echo_returns_message():
    assert echo.handler({"message": "hi"}, None) == {"echoed": "hi"}


def test_echo_rejects_missing_field():
    result = echo.handler({}, None)
    assert "error" in result


def test_get_time_returns_iso_utc_timestamp():
    result = get_time.handler({}, None)
    assert "utc_time" in result
    assert result["utc_time"].endswith("+00:00")


def test_get_time_ignores_none_event():
    result = get_time.handler(None, None)
    assert "utc_time" in result


def test_add_numbers_returns_sum():
    assert add_numbers.handler({"a": 2, "b": 3}, None) == {"result": 5}


def test_add_numbers_rejects_non_numeric_input():
    result = add_numbers.handler({"a": "x", "b": 3}, None)
    assert "error" in result
