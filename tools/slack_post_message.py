from pydantic import BaseModel, ValidationError

try:
    from tools import _slack_client
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _slack_client

NAME = "slack_post_message"
DESCRIPTION = (
    "Posts a message to a Slack channel. Requires the Slack bot to be invited to the "
    "target channel."
)


class SlackPostMessageInput(BaseModel):
    channel: str
    text: str


class SlackPostMessageOutput(BaseModel):
    ok: bool
    channel: str
    ts: str


def handler(event, context):
    try:
        parsed = SlackPostMessageInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}

    try:
        response = _slack_client.call(
            "chat.postMessage", {"channel": parsed.channel, "text": parsed.text}
        )
    except Exception as e:
        return {"error": str(e)}

    return SlackPostMessageOutput(
        ok=True, channel=response["channel"], ts=response["ts"]
    ).model_dump()
