"""Thin Slack Web API client shared by the slack_* tools.

Not a tool itself - has no NAME/DESCRIPTION/handler, so it's never included
in TOOLS/registry loops. The bot token lives in SSM (SecureString, name given
by the SLACK_BOT_TOKEN_SSM_PARAM env var - set by Terraform only for tools
with needs_slack_token = true) rather than a Lambda env var directly, and is
cached per warm Lambda execution environment to avoid a decrypt call on
every invocation. Uses urllib (stdlib) instead of requests/httpx so the
Slack tools don't need anything beyond the pydantic vendor already built for
every other tool.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import boto3

_SLACK_BOT_TOKEN_SSM_PARAM = os.environ.get("SLACK_BOT_TOKEN_SSM_PARAM", "")
_cached_token: str | None = None


def _get_token() -> str:
    global _cached_token
    if _cached_token is None:
        ssm = boto3.client("ssm")
        response = ssm.get_parameter(Name=_SLACK_BOT_TOKEN_SSM_PARAM, WithDecryption=True)
        _cached_token = response["Parameter"]["Value"]
    return _cached_token


def call(method: str, params: dict) -> dict:
    """Calls a Slack Web API method, raising RuntimeError on any non-ok response."""
    token = _get_token()
    data = urllib.parse.urlencode(params).encode()
    request = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode())

    if not payload.get("ok"):
        raise RuntimeError(f"Slack API error ({method}): {payload.get('error', 'unknown error')}")
    return payload
