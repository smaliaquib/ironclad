"""One-time local helper to get a Gmail OAuth2 refresh token.

Run this on your own machine (never in Lambda/CI) - it opens a browser for
you to log into Google and consent, then prints the SSM command to store the
resulting credentials. Not part of the deployed tools; needs its own
dependency, not part of this repo's main pyproject.toml:

    pip install google-auth-oauthlib

Usage:
    GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... python scripts/gmail_get_refresh_token.py

Prerequisite: a Google Cloud project with the Gmail API enabled and an OAuth
2.0 Client ID of type "Desktop app" (console.cloud.google.com -> APIs &
Services -> Credentials). Copy that client's ID/secret into the env vars
above.
"""

import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

# Minimal scopes matching what gmail_search/gmail_read (readonly) and
# gmail_send/gmail_reply (send) actually need - deliberately not the
# sweeping https://mail.google.com/ full-mailbox scope.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def main() -> None:
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET first.", file=sys.stderr)
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(port=0)

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": credentials.refresh_token,
    }

    print("\n=== Success - refresh token obtained ===\n")
    print("Run this to store it (fill in the SSM parameter name from `terraform output`):\n")
    print(
        "aws ssm put-parameter --name <gmail_credentials_ssm_parameter_name output> "
        f"--type SecureString --overwrite --value '{json.dumps(payload)}'"
    )


if __name__ == "__main__":
    main()
