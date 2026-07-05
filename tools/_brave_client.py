"""Thin Brave Search API client shared by the brave_* tools.

Not a tool itself - has no NAME/DESCRIPTION/handler. Unlike Gmail's OAuth2
flow, Brave Search auth is a single static API key (no expiry, no scopes to
reinstall) - so it's cached for the life of the warm execution environment,
same as the Slack bot token. The key lives in SSM (SecureString, name given
by the BRAVE_API_KEY_SSM_PARAM env var - set by Terraform only for tools
with needs_brave_api_key = true). Uses urllib (stdlib), no extra vendored
dependency.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import boto3

_BRAVE_API_KEY_SSM_PARAM = os.environ.get("BRAVE_API_KEY_SSM_PARAM", "")
_cached_api_key: str | None = None


def _get_api_key() -> str:
    global _cached_api_key
    if _cached_api_key is None:
        ssm = boto3.client("ssm")
        response = ssm.get_parameter(Name=_BRAVE_API_KEY_SSM_PARAM, WithDecryption=True)
        _cached_api_key = response["Parameter"]["Value"]
    return _cached_api_key


def call(path: str, params: dict) -> dict:
    """Calls a Brave Search API v1 endpoint, raising RuntimeError on any
    non-2xx response or non-JSON body.
    """
    api_key = _get_api_key()
    url = f"https://api.search.brave.com{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        raise RuntimeError(f"Brave Search API error ({path}): {e.code} {detail}") from e

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Brave Search API returned a non-JSON body ({path}): {raw[:300]!r}"
        ) from e
