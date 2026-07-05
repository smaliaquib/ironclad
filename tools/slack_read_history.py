from pydantic import BaseModel, Field, ValidationError

try:
    from tools import _slack_client
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _slack_client

NAME = "slack_read_history"
DESCRIPTION = (
    "Reads the most recent messages from a Slack channel. Requires the Slack bot to "
    "be a member of the channel."
)


class SlackReadHistoryInput(BaseModel):
    channel: str
    limit: int = Field(default=10, ge=1, le=100)


class SlackMessage(BaseModel):
    user: str = ""
    text: str = ""
    ts: str = ""


class SlackReadHistoryOutput(BaseModel):
    messages: list[SlackMessage]


def handler(event, context):
    try:
        parsed = SlackReadHistoryInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}

    try:
        response = _slack_client.call(
            "conversations.history", {"channel": parsed.channel, "limit": parsed.limit}
        )
    except Exception as e:
        return {"error": str(e)}

    messages = [
        SlackMessage(user=m.get("user", ""), text=m.get("text", ""), ts=m.get("ts", ""))
        for m in response.get("messages", [])
    ]
    return SlackReadHistoryOutput(messages=messages).model_dump()
