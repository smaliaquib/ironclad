from pydantic import BaseModel, ValidationError

try:
    from tools import _gmail_client
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _gmail_client

NAME = "gmail_send"
DESCRIPTION = (
    "Sends a new email from the connected Gmail account. Sends real mail - only "
    "use when explicitly asked to send an email."
)


class GmailSendInput(BaseModel):
    to: str
    subject: str
    body: str


class GmailSendOutput(BaseModel):
    id: str
    thread_id: str


def handler(event, context):
    try:
        parsed = GmailSendInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}

    try:
        raw = _gmail_client.build_raw_message(parsed.to, parsed.subject, parsed.body)
        response = _gmail_client.call("POST", "/messages/send", json_body={"raw": raw})
    except Exception as e:
        return {"error": str(e)}

    return GmailSendOutput(id=response["id"], thread_id=response["threadId"]).model_dump()
