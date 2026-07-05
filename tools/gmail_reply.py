from pydantic import BaseModel, ValidationError

try:
    from tools import _gmail_client
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _gmail_client

NAME = "gmail_reply"
DESCRIPTION = (
    "Replies to an existing Gmail message by id (from gmail_search/gmail_read), "
    "keeping it in the same thread. Sends real mail - only use when explicitly "
    "asked to reply."
)


class GmailReplyInput(BaseModel):
    message_id: str
    body: str


class GmailReplyOutput(BaseModel):
    id: str
    thread_id: str


def _headers_of(message: dict) -> dict[str, str]:
    return {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}


def handler(event, context):
    try:
        parsed = GmailReplyInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}

    try:
        original = _gmail_client.call(
            "GET",
            f"/messages/{parsed.message_id}",
            params={
                "format": "metadata",
                "metadataHeaders": ["Subject", "From", "Message-Id", "References"],
            },
        )
        headers = _headers_of(original)
        subject = headers.get("Subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        references = " ".join(
            filter(None, [headers.get("References", ""), headers.get("Message-Id", "")])
        )

        raw = _gmail_client.build_raw_message(
            to=headers.get("From", ""),
            subject=subject,
            body=parsed.body,
            extra_headers={
                "In-Reply-To": headers.get("Message-Id", ""),
                "References": references,
            },
        )
        response = _gmail_client.call(
            "POST",
            "/messages/send",
            json_body={"raw": raw, "threadId": original["threadId"]},
        )
    except Exception as e:
        return {"error": str(e)}

    return GmailReplyOutput(id=response["id"], thread_id=response["threadId"]).model_dump()
