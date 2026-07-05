from pydantic import BaseModel, Field, ValidationError

try:
    from tools import _brave_client
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _brave_client

NAME = "brave_web_search"
DESCRIPTION = (
    "Searches the live web via Brave Search - general research, product/price "
    "comparisons, documentation lookups, anything needing current information "
    "beyond the model's training data."
)


class BraveWebSearchInput(BaseModel):
    query: str
    count: int = Field(default=10, ge=1, le=20)


class BraveWebSearchResult(BaseModel):
    title: str = ""
    url: str = ""
    description: str = ""


class BraveWebSearchOutput(BaseModel):
    results: list[BraveWebSearchResult]


def handler(event, context):
    try:
        parsed = BraveWebSearchInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}

    try:
        response = _brave_client.call(
            "/res/v1/web/search", {"q": parsed.query, "count": parsed.count}
        )
    except Exception as e:
        return {"error": str(e)}

    raw_results = response.get("web", {}).get("results", [])
    results = [
        BraveWebSearchResult(
            title=r.get("title", ""), url=r.get("url", ""), description=r.get("description", "")
        )
        for r in raw_results
    ]
    return BraveWebSearchOutput(results=results).model_dump()
