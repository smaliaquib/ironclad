from pydantic import BaseModel, Field, ValidationError

try:
    from tools import _brave_client
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _brave_client

NAME = "brave_news_search"
DESCRIPTION = (
    "Searches recent news via Brave Search - current events, breaking news, "
    "time-sensitive topics."
)


class BraveNewsSearchInput(BaseModel):
    query: str
    count: int = Field(default=10, ge=1, le=20)


class BraveNewsSearchResult(BaseModel):
    title: str = ""
    url: str = ""
    description: str = ""
    age: str = ""


class BraveNewsSearchOutput(BaseModel):
    results: list[BraveNewsSearchResult]


def handler(event, context):
    try:
        parsed = BraveNewsSearchInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}

    try:
        response = _brave_client.call(
            "/res/v1/news/search", {"q": parsed.query, "count": parsed.count}
        )
    except Exception as e:
        return {"error": str(e)}

    raw_results = response.get("results", [])
    results = [
        BraveNewsSearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            description=r.get("description", ""),
            age=r.get("age", ""),
        )
        for r in raw_results
    ]
    return BraveNewsSearchOutput(results=results).model_dump()
