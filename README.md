
# Ironclad — mcp-tools

The Lambda-backed MCP tools for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview. These tools are called by the `mcp-gateway` service, which reads their catalog from an SSM Parameter (the "tool registry") that this repo's own CD pipeline writes on every deploy.

Three deliberately trivial ("dummy") tools proving the gateway's Lambda dispatch works end-to-end, plus three real Slack tools:

| Tool | Input | Output |
|---|---|---|
| `echo` | `{ "message": string }` | `{ "echoed": string }` |
| `get_time` | `{}` | `{ "utc_time": string }` (ISO 8601 UTC) |
| `add_numbers` | `{ "a": number, "b": number }` | `{ "result": number }` |
| `slack_post_message` | `{ "channel": string, "text": string }` | `{ "ok": bool, "channel": string, "ts": string }` |
| `slack_read_history` | `{ "channel": string, "limit"?: number (1-100, default 10) }` | `{ "messages": [{ "user": string, "text": string, "ts": string }] }` |
| `slack_list_channels` | `{}` | `{ "channels": [{ "id": string, "name": string }] }` |

Each tool defines a [Pydantic](https://docs.pydantic.dev/) `BaseModel` for its input and validates every call against it - a bad call gets back `{"error": "..."}` instead of crashing the Lambda. There is no hand-written JSON Schema anywhere in this repo or in `infra`: the schema published in the tool registry is generated directly from these models (`model_json_schema()`), so what the gateway advertises can never drift from what the Lambda actually accepts.

### Slack tools setup

The three `slack_*` tools share `tools/_slack_client.py`, a thin Slack Web API client (stdlib `urllib`, no extra vendored dependency). It reads the bot token from SSM (SecureString) at call time, cached per warm Lambda execution environment. `infra`'s `modules/mcp-tools` creates the SSM parameter shell and grants exactly these 3 functions `ssm:GetParameter` + `kms:Decrypt` - it never sets the real value (`lifecycle { ignore_changes = [value] }`, same ownership pattern as the tool registry). One-time manual setup after `terraform apply`:

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps), add the `chat:write`, `channels:history`, and `channels:read` bot token scopes, install it to your workspace, and invite the bot to whichever channels it should read/post in.
2. `aws ssm put-parameter --name <slack_bot_token_ssm_parameter_name output> --type SecureString --value xoxb-... --overwrite`

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

`infra`'s `modules/mcp-tools` creates each tool's `aws_lambda_function` (IAM role + a placeholder zip only - `lifecycle { ignore_changes = [filename, source_code_hash] }`) and the registry `aws_ssm_parameter` (also placeholder, `ignore_changes = [value]`). Neither the real code nor the real registry content ever comes from Terraform - both come from this repo's own CD pipeline, same principle as how the ECS-based services (`frontend`/`router`/`agent`/`mcp-gateway`) get their container image from their own CD, not from `terraform apply`. The 3 Slack tools additionally get a `SLACK_BOT_TOKEN_SSM_PARAM` env var and an inline IAM policy for the Slack token parameter, gated by `needs_slack_token = true` on that tool's entry in `mcp_gateway_tools`.

## CI/CD

`buildspecs/buildspec-ci.yml` - lint (ruff) + format check (black) + unit tests (pytest) + schema-drift check, meant to run on PRs/feature branch pushes.

`buildspecs/buildspec-cd.yml`, on merges to this branch:
1. Vendors `pydantic` (and its compiled dependency `pydantic-core`) into each tool's deployment zip via `pip install --platform manylinux2014_x86_64 --only-binary=:all:` - the base Python 3.12 Lambda runtime doesn't include it, and this fetches the correct prebuilt wheel regardless of the CodeBuild host's own platform. `boto3` needs no vendoring - it ships with the Lambda runtime already.
2. `aws lambda update-function-code`s each of the 6 functions (the 3 `slack_*` zips also bundle `tools/_slack_client.py`).
3. Regenerates the schemas, looks up each function's real ARN (`aws lambda get-function`), and `aws ssm put-parameter --overwrite`s the tool registry with the fresh `{name, description, input_schema, lambda_arn}` catalog.

Expects `AWS_DEFAULT_REGION`, `NAME_PREFIX`, and `REGISTRY_SSM_PARAM` as CodeBuild environment variables (wired up in the `infra` branch). Every deploy writes exactly one new SSM parameter version - `aws ssm get-parameter-history --name <REGISTRY_SSM_PARAM>` shows the full history, one entry per deploy.
