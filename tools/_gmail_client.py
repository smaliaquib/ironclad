"""Thin Gmail API v1 client shared by the gmail_* tools.

Not a tool itself - has no NAME/DESCRIPTION/handler. OAuth2 credentials
(client_id, client_secret, refresh_token) live in SSM (SecureString, name
given by the GMAIL_CREDENTIALS_SSM_PARAM env var - set by Terraform only for
tools with needs_gmail_credentials = true) as a single JSON blob, generated
once via scripts/gmail_get_refresh_token.py (run locally on your own machine,
not in Lambda - see the README). Uses urllib (stdlib) instead of the Google
API client libraries so the Gmail tools don't need anything beyond the
pydantic vendor already built for every other tool.

The refresh_token is cached for the life of the warm execution environment
(it doesn't expire on its own, only on user revocation), but the short-lived
access token it exchanges for is cached with its own expiry and re-exchanged
once that expires - unlike a naive "cache forever," this can't silently keep
serving a stale token past its real lifetime.
"""

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from email.mime.text import MIMEText

import boto3

_GMAIL_CREDENTIALS_SSM_PARAM = os.environ.get("GMAIL_CREDENTIALS_SSM_PARAM", "")
_cached_credentials: dict | None = None
_cached_access_token: str | None = None
_access_token_expires_at: float = 0.0


def _get_credentials() -> dict:
    global _cached_credentials
    if _cached_credentials is None:
        ssm = boto3.client("ssm")
        response = ssm.get_parameter(Name=_GMAIL_CREDENTIALS_SSM_PARAM, WithDecryption=True)
        _cached_credentials = json.loads(response["Parameter"]["Value"])
    return _cached_credentials


def _get_access_token() -> str:
    global _cached_access_token, _access_token_expires_at
    if _cached_access_token and time.time() < _access_token_expires_at:
        return _cached_access_token

    creds = _get_credentials()
    data = urllib.parse.urlencode(
        {
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token",
        }
    ).encode()
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode())

    _cached_access_token = payload["access_token"]
    _access_token_expires_at = time.time() + payload.get("expires_in", 3600) - 60
    return _cached_access_token


def call(method: str, path: str, params: dict | None = None, json_body: dict | None = None) -> dict:
    """Calls a Gmail API v1 endpoint (users/me<path>), raising RuntimeError on
    any non-2xx response.
    """
    token = _get_access_token()
    url = f"https://gmail.googleapis.com/gmail/v1/users/me{path}"
    if params:
        url += f"?{urllib.parse.urlencode(params, doseq=True)}"
    data = json.dumps(json_body).encode() if json_body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        raise RuntimeError(f"Gmail API error ({method} {path}): {e.code} {detail}") from e


def build_raw_message(
    to: str, subject: str, body: str, extra_headers: dict[str, str] | None = None
) -> str:
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    for key, value in (extra_headers or {}).items():
        if value:
            message[key] = value
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


def decode_body_data(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
