from pydantic import BaseModel, ValidationError

try:
    from tools import _gmail_client
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _gmail_client

NAME = "gmail_read"
DESCRIPTION = (
    "Reads one Gmail message by id (from gmail_search results) and returns its "
    "subject, sender, recipient, date, and plain-text body."
)


class GmailReadInput(BaseModel):
    message_id: str


class GmailReadOutput(BaseModel):
    subject: str = ""
    sender: str = ""
    to: str = ""
    date: str = ""
    snippet: str = ""
    body: str = ""


def _headers_of(message: dict) -> dict[str, str]:
    return {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}


def _find_plain_text(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            return _gmail_client.decode_body_data(data)
    for part in payload.get("parts", []) or []:
        text = _find_plain_text(part)
        if text:
            return text
    return ""


def handler(event, context):
    try:
        parsed = GmailReadInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}

    try:
        message = _gmail_client.call(
            "GET", f"/messages/{parsed.message_id}", params={"format": "full"}
        )
    except Exception as e:
        return {"error": str(e)}

    headers = _headers_of(message)
    body = _find_plain_text(message.get("payload", {})) or message.get("snippet", "")

    return GmailReadOutput(
        subject=headers.get("Subject", ""),
        sender=headers.get("From", ""),
        to=headers.get("To", ""),
        date=headers.get("Date", ""),
        snippet=message.get("snippet", ""),
        body=body,
    ).model_dump()
