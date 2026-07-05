from pydantic import BaseModel, ValidationError

try:
    from tools import _slack_client
except ImportError:  # deployed Lambda zip flattens tools/ to the package root
    import _slack_client

NAME = "slack_list_channels"
DESCRIPTION = (
    "Lists the Slack channels visible to the bot (public channels it can see, plus "
    "any private channels it has been invited to)."
)


class SlackListChannelsInput(BaseModel):
    pass


class SlackChannel(BaseModel):
    id: str
    name: str


class SlackListChannelsOutput(BaseModel):
    channels: list[SlackChannel]


def handler(event, context):
    try:
        SlackListChannelsInput.model_validate(event or {})
    except ValidationError as e:
        return {"error": str(e)}

    try:
        response = _slack_client.call("conversations.list", {})
    except Exception as e:
        return {"error": str(e)}

    channels = [SlackChannel(id=c["id"], name=c["name"]) for c in response.get("channels", [])]
    return SlackListChannelsOutput(channels=channels).model_dump()
