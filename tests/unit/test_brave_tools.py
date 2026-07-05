from tools import _brave_client, brave_news_search, brave_web_search


def test_brave_web_search_returns_results(monkeypatch):
    calls = []

    def fake_call(path, params):
        calls.append((path, params))
        return {
            "web": {
                "results": [
                    {"title": "Result 1", "url": "https://a.com", "description": "desc 1"},
                    {"title": "Result 2", "url": "https://b.com", "description": "desc 2"},
                ]
            }
        }

    monkeypatch.setattr(_brave_client, "call", fake_call)

    result = brave_web_search.handler({"query": "python"}, None)

    assert result == {
        "results": [
            {"title": "Result 1", "url": "https://a.com", "description": "desc 1"},
            {"title": "Result 2", "url": "https://b.com", "description": "desc 2"},
        ]
    }
    assert calls[0] == ("/res/v1/web/search", {"q": "python", "count": 10})


def test_brave_web_search_rejects_missing_query():
    result = brave_web_search.handler({}, None)
    assert "error" in result


def test_brave_web_search_surfaces_api_error(monkeypatch):
    def raise_error(path, params):
        raise RuntimeError("Brave Search API error (/res/v1/web/search): 401 unauthorized")

    monkeypatch.setattr(_brave_client, "call", raise_error)

    result = brave_web_search.handler({"query": "python"}, None)
    assert "error" in result


def test_brave_web_search_handles_missing_web_key(monkeypatch):
    monkeypatch.setattr(_brave_client, "call", lambda path, params: {})

    result = brave_web_search.handler({"query": "python"}, None)

    assert result == {"results": []}


def test_brave_news_search_returns_results(monkeypatch):
    calls = []

    def fake_call(path, params):
        calls.append((path, params))
        return {
            "results": [
                {
                    "title": "Breaking news",
                    "url": "https://news.com/1",
                    "description": "desc",
                    "age": "2 hours ago",
                }
            ]
        }

    monkeypatch.setattr(_brave_client, "call", fake_call)

    result = brave_news_search.handler({"query": "elections", "count": 5}, None)

    assert result == {
        "results": [
            {
                "title": "Breaking news",
                "url": "https://news.com/1",
                "description": "desc",
                "age": "2 hours ago",
            }
        ]
    }
    assert calls[0] == ("/res/v1/news/search", {"q": "elections", "count": 5})


def test_brave_news_search_rejects_missing_query():
    result = brave_news_search.handler({}, None)
    assert "error" in result


def test_brave_news_search_rejects_count_out_of_range():
    result = brave_news_search.handler({"query": "x", "count": 100}, None)
    assert "error" in result
