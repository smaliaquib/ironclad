import urllib.parse
import urllib.request
from html.parser import HTMLParser

from pydantic import BaseModel, Field, ValidationError

try:
    from tools import _web_utils
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _web_utils

NAME = "duckduckgo_search"
DESCRIPTION = (
    "Searches the live web via DuckDuckGo (unofficial HTML results page, no "
    "API key needed) - general research, news, price comparisons, anything "
    "needing current information beyond the model's training data."
)


class DuckDuckGoSearchInput(BaseModel):
    query: str
    count: int = Field(default=10, ge=1, le=20)


class DuckDuckGoSearchResult(BaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""


class DuckDuckGoSearchOutput(BaseModel):
    results: list[DuckDuckGoSearchResult]


class _ResultParser(HTMLParser):
    """Parses DuckDuckGo's lite HTML results page. Each result is an
    <a class="result__a" href="..."> (title + wrapped real URL) followed by
    an <a class="result__snippet"> (description), in that document order.
    """

    def __init__(self):
        super().__init__()
        self.results: list[dict] = []
        self._current: dict | None = None
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "").split()
        if tag == "a" and "result__a" in classes:
            self._current = {
                "title": "",
                "url": self._real_url(attrs_dict.get("href", "")),
                "snippet": "",
            }
            self.results.append(self._current)
            self._capture_title = True
        elif tag == "a" and "result__snippet" in classes:
            self._capture_snippet = True

    def handle_endtag(self, tag):
        if tag == "a":
            self._capture_title = False
            self._capture_snippet = False

    def handle_data(self, data):
        if self._current is None:
            return
        if self._capture_title:
            self._current["title"] += data
        elif self._capture_snippet:
            self._current["snippet"] += data

    @staticmethod
    def _real_url(href: str) -> str:
        # DuckDuckGo wraps outbound links: //duckduckgo.com/l/?uddg=<encoded-url>&...
        if "uddg=" in href:
            full = href if href.startswith("http") else f"https:{href}"
            query = urllib.parse.parse_qs(urllib.parse.urlparse(full).query)
            if "uddg" in query:
                return query["uddg"][0]
        return href


def handler(event, context):
    try:
        parsed = DuckDuckGoSearchInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}

    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(parsed.query)}"
    request = urllib.request.Request(url, headers={"User-Agent": _web_utils.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            html = response.read().decode("utf-8", errors="replace")
    except Exception as e:
        return {"error": str(e)}

    parser = _ResultParser()
    parser.feed(html)
    results = [
        DuckDuckGoSearchResult(title=r["title"].strip(), url=r["url"], snippet=r["snippet"].strip())
        for r in parser.results[: parsed.count]
    ]
    return DuckDuckGoSearchOutput(results=results).model_dump()
