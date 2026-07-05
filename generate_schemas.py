"""Regenerates schemas.generated.json from each tool's Pydantic Input model.

Run this after editing any tool's Input model, then commit the result:

    uv run python generate_schemas.py

CI re-runs this to a temp file and diffs it against the committed copy, so a
tool's published schema can never silently drift from what it actually
validates at call time.
"""

import json
from pathlib import Path

from tools.add_numbers import NAME as ADD_NUMBERS_NAME
from tools.add_numbers import AddNumbersInput
from tools.duckduckgo_fetch import NAME as DUCKDUCKGO_FETCH_NAME
from tools.duckduckgo_fetch import DuckDuckGoFetchInput
from tools.duckduckgo_search import NAME as DUCKDUCKGO_SEARCH_NAME
from tools.duckduckgo_search import DuckDuckGoSearchInput
from tools.echo import NAME as ECHO_NAME
from tools.echo import EchoInput
from tools.get_time import NAME as GET_TIME_NAME
from tools.get_time import GetTimeInput
from tools.gmail_read import NAME as GMAIL_READ_NAME
from tools.gmail_read import GmailReadInput
from tools.gmail_reply import NAME as GMAIL_REPLY_NAME
from tools.gmail_reply import GmailReplyInput
from tools.gmail_search import NAME as GMAIL_SEARCH_NAME
from tools.gmail_search import GmailSearchInput
from tools.gmail_send import NAME as GMAIL_SEND_NAME
from tools.gmail_send import GmailSendInput
from tools.slack_list_channels import NAME as SLACK_LIST_CHANNELS_NAME
from tools.slack_list_channels import SlackListChannelsInput
from tools.slack_post_message import NAME as SLACK_POST_MESSAGE_NAME
from tools.slack_post_message import SlackPostMessageInput
from tools.slack_read_history import NAME as SLACK_READ_HISTORY_NAME
from tools.slack_read_history import SlackReadHistoryInput

OUTPUT_PATH = Path(__file__).parent / "schemas.generated.json"


def main() -> None:
    schemas = {
        ECHO_NAME: EchoInput.model_json_schema(),
        GET_TIME_NAME: GetTimeInput.model_json_schema(),
        ADD_NUMBERS_NAME: AddNumbersInput.model_json_schema(),
        SLACK_POST_MESSAGE_NAME: SlackPostMessageInput.model_json_schema(),
        SLACK_READ_HISTORY_NAME: SlackReadHistoryInput.model_json_schema(),
        SLACK_LIST_CHANNELS_NAME: SlackListChannelsInput.model_json_schema(),
        GMAIL_SEARCH_NAME: GmailSearchInput.model_json_schema(),
        GMAIL_READ_NAME: GmailReadInput.model_json_schema(),
        GMAIL_SEND_NAME: GmailSendInput.model_json_schema(),
        GMAIL_REPLY_NAME: GmailReplyInput.model_json_schema(),
        DUCKDUCKGO_SEARCH_NAME: DuckDuckGoSearchInput.model_json_schema(),
        DUCKDUCKGO_FETCH_NAME: DuckDuckGoFetchInput.model_json_schema(),
    }
    OUTPUT_PATH.write_text(json.dumps(schemas, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
