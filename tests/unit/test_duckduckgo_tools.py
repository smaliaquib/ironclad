import urllib.error

from tools import duckduckgo_fetch, duckduckgo_search

SAMPLE_RESULTS_HTML = """
<html><body>
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage1">
    Example Page One
  </a>
  <a class="result__snippet">This is the first snippet.</a>
</div>
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage2">
    Example Page Two
  </a>
  <a class="result__snippet">This is the second snippet.</a>
</div>
</body></html>
"""


class FakeHTTPResponse:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_duckduckgo_search_parses_results_and_unwraps_urls(monkeypatch):
    monkeypatch.setattr(
        duckduckgo_search.urllib.request,
        "urlopen",
        lambda request, timeout=15: FakeHTTPResponse(SAMPLE_RESULTS_HTML),
    )

    result = duckduckgo_search.handler({"query": "test query"}, None)

    assert result == {
        "results": [
            {
                "title": "Example Page One",
                "url": "https://example.com/page1",
                "snippet": "This is the first snippet.",
            },
            {
                "title": "Example Page Two",
                "url": "https://example.com/page2",
                "snippet": "This is the second snippet.",
            },
        ]
    }


def test_duckduckgo_search_respects_count(monkeypatch):
    monkeypatch.setattr(
        duckduckgo_search.urllib.request,
        "urlopen",
        lambda request, timeout=15: FakeHTTPResponse(SAMPLE_RESULTS_HTML),
    )

    result = duckduckgo_search.handler({"query": "test query", "count": 1}, None)

    assert len(result["results"]) == 1


def test_duckduckgo_search_rejects_missing_query():
    result = duckduckgo_search.handler({}, None)
    assert "error" in result


def test_duckduckgo_search_surfaces_fetch_failure(monkeypatch):
    def raise_error(request, timeout=15):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(duckduckgo_search.urllib.request, "urlopen", raise_error)

    result = duckduckgo_search.handler({"query": "test"}, None)
    assert "error" in result


def test_duckduckgo_fetch_returns_cleaned_content(monkeypatch):
    html = "<html><head><title>My Page</title></head><body><p>Hello world</p></body></html>"
    monkeypatch.setattr(
        duckduckgo_fetch.urllib.request,
        "urlopen",
        lambda request, timeout=15: FakeHTTPResponse(html),
    )

    result = duckduckgo_fetch.handler({"url": "https://example.com"}, None)

    assert result == {
        "url": "https://example.com",
        "title": "My Page",
        "content": "My Page Hello world",
    }


def test_duckduckgo_fetch_truncates_to_max_chars(monkeypatch):
    html = f"<html><body><p>{'x' * 10000}</p></body></html>"
    monkeypatch.setattr(
        duckduckgo_fetch.urllib.request,
        "urlopen",
        lambda request, timeout=15: FakeHTTPResponse(html),
    )

    result = duckduckgo_fetch.handler({"url": "https://example.com", "max_chars": 500}, None)

    assert len(result["content"]) == 500


def test_duckduckgo_fetch_rejects_non_http_scheme():
    result = duckduckgo_fetch.handler({"url": "ftp://example.com"}, None)
    assert "error" in result


def test_duckduckgo_fetch_rejects_missing_url():
    result = duckduckgo_fetch.handler({}, None)
    assert "error" in result
