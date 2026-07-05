
# Ironclad — mcp-tools

The Lambda-backed MCP tools for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview. These tools are called by the `mcp-gateway` service, which reads their catalog from an SSM Parameter (the "tool registry") that this repo's own CD pipeline writes on every deploy.

Three deliberately trivial ("dummy") tools proving the gateway's Lambda dispatch works end-to-end, plus real Slack, Gmail, and DuckDuckGo tools:

| Tool | Input | Output |
|---|---|---|
| `echo` | `{ "message": string }` | `{ "echoed": string }` |
| `get_time` | `{}` | `{ "utc_time": string }` (ISO 8601 UTC) |
| `add_numbers` | `{ "a": number, "b": number }` | `{ "result": number }` |
| `slack_post_message` | `{ "channel": string, "text": string }` | `{ "ok": bool, "channel": string, "ts": string }` |
| `slack_read_history` | `{ "channel": string, "limit"?: number (1-100, default 10) }` | `{ "messages": [{ "user": string, "text": string, "ts": string }] }` |
| `slack_list_channels` | `{}` | `{ "channels": [{ "id": string, "name": string }] }` |
| `gmail_search` | `{ "query": string, "max_results"?: number (1-25, default 10) }` | `{ "results": [{ "id", "thread_id", "subject", "sender", "date", "snippet" }] }` |
| `gmail_read` | `{ "message_id": string }` | `{ "subject", "sender", "to", "date", "snippet", "body" }` |
| `gmail_send` | `{ "to": string, "subject": string, "body": string }` | `{ "id": string, "thread_id": string }` |
| `gmail_reply` | `{ "message_id": string, "body": string }` | `{ "id": string, "thread_id": string }` |
| `duckduckgo_search` | `{ "query": string, "count"?: number (1-20, default 10) }` | `{ "results": [{ "title", "url", "snippet" }] }` |
| `duckduckgo_fetch` | `{ "url": string, "max_chars"?: number (500-20000, default 5000) }` | `{ "url", "title", "content" }` |

Each tool defines a [Pydantic](https://docs.pydantic.dev/) `BaseModel` for its input and validates every call against it - a bad call gets back `{"error": "..."}` instead of crashing the Lambda. There is no hand-written JSON Schema anywhere in this repo or in `infra`: the schema published in the tool registry is generated directly from these models (`model_json_schema()`), so what the gateway advertises can never drift from what the Lambda actually accepts.

### Slack tools setup

The three `slack_*` tools share `tools/_slack_client.py`, a thin Slack Web API client (stdlib `urllib`, no extra vendored dependency). It reads the bot token from SSM (SecureString) at call time, cached per warm Lambda execution environment. `infra`'s `modules/mcp-tools` creates the SSM parameter shell and grants exactly these 3 functions `ssm:GetParameter` + `kms:Decrypt` - it never sets the real value (`lifecycle { ignore_changes = [value] }`, same ownership pattern as the tool registry). One-time manual setup after `terraform apply`:

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps), add the `chat:write`, `channels:history`, and `channels:read` bot token scopes, install it to your workspace, and invite the bot to whichever channels it should read/post in.
2. `aws ssm put-parameter --name <slack_bot_token_ssm_parameter_name output> --type SecureString --value xoxb-... --overwrite`

### Gmail tools setup

The four `gmail_*` tools share `tools/_gmail_client.py`, a thin Gmail API v1 client (stdlib `urllib`, no extra vendored dependency). It exchanges a refresh token for a short-lived access token via Google's OAuth2 endpoint, caching the access token only until it actually expires (not indefinitely) - `_get_credentials()`/`_get_access_token()` in that file. Credentials (`client_id`, `client_secret`, `refresh_token`) live as one JSON blob in SSM (SecureString), same placeholder-shell ownership pattern as the Slack token: `infra` creates it, this repo's code never writes it, and it grants exactly these 4 functions `ssm:GetParameter` + `kms:Decrypt`, gated by `needs_gmail_credentials = true`.

Scopes requested are deliberately minimal: `gmail.readonly` (search/read) and `gmail.send` (send/reply) - not the sweeping `https://mail.google.com/` full-mailbox scope.

One-time manual setup (the OAuth consent step needs a real browser + your Google login, so this can't be automated):

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project (or use an existing one), enable the **Gmail API**, and create an OAuth 2.0 Client ID of type **Desktop app** under APIs & Services → Credentials. Note the client ID and secret.
2. Locally (not in this repo's CI/CD): `pip install google-auth-oauthlib`, then run:
   ```
   GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... python scripts/gmail_get_refresh_token.py
   ```
   This opens a browser for you to log in and consent, then prints the refresh token and a ready-to-run `aws ssm put-parameter` command.
3. Run the printed command (fill in `<gmail_credentials_ssm_parameter_name output>` from `terraform output` in the `infra` branch) to store `{client_id, client_secret, refresh_token}` in SSM.

Google refresh tokens for apps still in "Testing" publishing status expire after 7 days - either add yourself as a test user and re-run step 2 periodically, or publish the OAuth consent screen (still fine for personal single-user use) to get a non-expiring refresh token.

### DuckDuckGo tools setup

No credentials, no SSM parameter, no IAM grant - `duckduckgo_search` and `duckduckgo_fetch` share `tools/_web_utils.py` (stdlib `html.parser`-based HTML-to-text stripping, no vendored dependency) and need nothing beyond the standard basic execution role every tool gets.

**Important caveat:** DuckDuckGo has no official general web-search API - only a free "Instant Answer" API (definitions/infoboxes, no ranked result list, not useful for open-ended research/news/price-comparison queries). `duckduckgo_search` instead screen-scrapes `html.duckduckgo.com/html`, DuckDuckGo's own lite results page: unofficial, against their Terms of Service, and liable to break without notice if they change markup or start blocking the request pattern - chosen deliberately anyway, in place of a paid provider (Brave Search's API stopped being viable for this project's free-tier use) or the much weaker official Instant Answer API. `duckduckgo_fetch` fetches an arbitrary `http(s)://` URL and returns cleaned, readable text (all HTML stripped) - meant to be used after `duckduckgo_search` to read a result in full.

## Run tools locally

```
uv sync
uv run python -c "from tools.echo import handler; print(handler({'message': 'hi'}, None))"
```

## Regenerating schemas

Run this after editing any tool's Pydantic model, and commit the result:

```
uv run python generate_schemas.py
```

CI (`buildspecs/buildspec-ci.yml`) re-runs this and diffs it against the committed `schemas.generated.json`, failing the build if they don't match - this is what actually prevents a model change from silently going out without its schema being regenerated.

## Lint, format, test

```
uv sync --frozen
uv run ruff check .
uv run black --check .
uv run pytest tests/unit/ -v
```

## Infra

`infra`'s `modules/mcp-tools` creates each tool's `aws_lambda_function` (IAM role + a placeholder zip only - `lifecycle { ignore_changes = [filename, source_code_hash] }`) and the registry `aws_ssm_parameter` (also placeholder, `ignore_changes = [value]`). Neither the real code nor the real registry content ever comes from Terraform - both come from this repo's own CD pipeline, same principle as how the ECS-based services (`frontend`/`router`/`agent`/`mcp-gateway`) get their container image from their own CD, not from `terraform apply`. The 3 Slack tools additionally get a `SLACK_BOT_TOKEN_SSM_PARAM` env var and an inline IAM policy for the Slack token parameter, gated by `needs_slack_token = true`; the 4 Gmail tools get `GMAIL_CREDENTIALS_SSM_PARAM` and the equivalent IAM grant, gated by `needs_gmail_credentials = true`. The 2 DuckDuckGo tools need neither - no credentials at all.

## CI/CD

`buildspecs/buildspec-ci.yml` - lint (ruff) + format check (black) + unit tests (pytest) + schema-drift check, meant to run on PRs/feature branch pushes.

`buildspecs/buildspec-cd.yml`, on merges to this branch:
1. Vendors `pydantic` (and its compiled dependency `pydantic-core`) into each tool's deployment zip via `pip install --platform manylinux2014_x86_64 --only-binary=:all:` - the base Python 3.12 Lambda runtime doesn't include it, and this fetches the correct prebuilt wheel regardless of the CodeBuild host's own platform. `boto3` needs no vendoring - it ships with the Lambda runtime already.
2. `aws lambda update-function-code`s each of the 12 functions (the 3 `slack_*` zips also bundle `tools/_slack_client.py`, the 4 `gmail_*` zips also bundle `tools/_gmail_client.py`, the 2 `duckduckgo_*` zips also bundle `tools/_web_utils.py`).
3. Regenerates the schemas, looks up each function's real ARN (`aws lambda get-function`), and `aws ssm put-parameter --overwrite`s the tool registry with the fresh `{name, description, input_schema, lambda_arn}` catalog.

Expects `AWS_DEFAULT_REGION`, `NAME_PREFIX`, and `REGISTRY_SSM_PARAM` as CodeBuild environment variables (wired up in the `infra` branch). Every deploy writes exactly one new SSM parameter version - `aws ssm get-parameter-history --name <REGISTRY_SSM_PARAM>` shows the full history, one entry per deploy.
