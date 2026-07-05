"""Shared HTML-scraping helpers for the duckduckgo_* tools. Not a tool itself.

DuckDuckGo has no official general web-search API - only a free "Instant
Answer" API (definitions/infoboxes, no ranked result list). html.duckduckgo.com/html
is DuckDuckGo's own lite HTML results page: no API key needed, but this is
screen-scraping their HTML, not a documented API - it can break if they
change markup, and is technically against their Terms of Service. Chosen
deliberately anyway per explicit request, in place of the official but much
weaker Instant Answer API.
"""

import re
from html.parser import HTMLParser

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self.chunks.append(data.strip())


def strip_tags(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.chunks)).strip()
