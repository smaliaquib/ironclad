import re
import urllib.request

from pydantic import BaseModel, Field, ValidationError

try:
    from tools import _web_utils
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _web_utils

NAME = "duckduckgo_fetch"
DESCRIPTION = (
    "Fetches a web page by URL and returns its cleaned, readable text content "
    "(HTML stripped) - use after duckduckgo_search to read a result in full."
)

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


class DuckDuckGoFetchInput(BaseModel):
    url: str
    max_chars: int = Field(default=5000, ge=500, le=20000)


class DuckDuckGoFetchOutput(BaseModel):
    url: str
    title: str = ""
    content: str = ""


def handler(event, context):
    try:
        parsed = DuckDuckGoFetchInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}

    if not parsed.url.startswith(("http://", "https://")):
        return {"error": "url must start with http:// or https://"}

    request = urllib.request.Request(parsed.url, headers={"User-Agent": _web_utils.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            html = response.read().decode("utf-8", errors="replace")
    except Exception as e:
        return {"error": str(e)}

    title_match = _TITLE_RE.search(html)
    title = _web_utils.strip_tags(title_match.group(1)) if title_match else ""
    content = _web_utils.strip_tags(html)[: parsed.max_chars]

    return DuckDuckGoFetchOutput(url=parsed.url, title=title, content=content).model_dump()
