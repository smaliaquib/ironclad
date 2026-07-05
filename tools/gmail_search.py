from pydantic import BaseModel, Field, ValidationError

try:
    from tools import _gmail_client
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _gmail_client

NAME = "gmail_search"
DESCRIPTION = (
    "Searches the Gmail inbox using Gmail search syntax (e.g. 'from:alice is:unread "
    "subject:invoice') and returns each matching message's id, subject, sender, "
    "date, and snippet."
)


class GmailSearchInput(BaseModel):
    query: str
    max_results: int = Field(default=10, ge=1, le=25)


class GmailSearchResult(BaseModel):
    id: str
    thread_id: str
    subject: str = ""
    sender: str = ""
    date: str = ""
    snippet: str = ""


class GmailSearchOutput(BaseModel):
    results: list[GmailSearchResult]


def _headers_of(message: dict) -> dict[str, str]:
    return {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}


def handler(event, context):
    try:
        parsed = GmailSearchInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}

    try:
        listing = _gmail_client.call(
            "GET", "/messages", params={"q": parsed.query, "maxResults": parsed.max_results}
        )
        results = []
        for m in listing.get("messages", []):
            message = _gmail_client.call(
                "GET",
                f"/messages/{m['id']}",
                params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
            )
            headers = _headers_of(message)
            results.append(
                GmailSearchResult(
                    id=message["id"],
                    thread_id=message["threadId"],
                    subject=headers.get("Subject", ""),
                    sender=headers.get("From", ""),
                    date=headers.get("Date", ""),
                    snippet=message.get("snippet", ""),
                )
            )
    except Exception as e:
        return {"error": str(e)}

    return GmailSearchOutput(results=results).model_dump()
