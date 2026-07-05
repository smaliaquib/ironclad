
# Ironclad — mcp-tools

The Lambda-backed MCP tools for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview. These tools are called by the `mcp-gateway` service, which reads their catalog from an SSM Parameter (the "tool registry") that this repo's own CD pipeline writes on every deploy.

Three deliberately trivial ("dummy") tools proving the gateway's Lambda dispatch works end-to-end:

| Tool | Input | Output |
|---|---|---|
| `echo` | `{ "message": string }` | `{ "echoed": string }` |
| `get_time` | `{}` | `{ "utc_time": string }` (ISO 8601 UTC) |
| `add_numbers` | `{ "a": number, "b": number }` | `{ "result": number }` |

Each tool defines a [Pydantic](https://docs.pydantic.dev/) `BaseModel` for its input and validates every call against it - a bad call gets back `{"error": "..."}` instead of crashing the Lambda. There is no hand-written JSON Schema anywhere in this repo or in `infra`: the schema published in the tool registry is generated directly from these models (`model_json_schema()`), so what the gateway advertises can never drift from what the Lambda actually accepts.

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

`infra`'s `modules/mcp-tools` creates each tool's `aws_lambda_function` (IAM role + a placeholder zip only - `lifecycle { ignore_changes = [filename, source_code_hash] }`) and the registry `aws_ssm_parameter` (also placeholder, `ignore_changes = [value]`). Neither the real code nor the real registry content ever comes from Terraform - both come from this repo's own CD pipeline, same principle as how the ECS-based services (`frontend`/`router`/`agent`/`mcp-gateway`) get their container image from their own CD, not from `terraform apply`.

## CI/CD

`buildspecs/buildspec-ci.yml` - lint (ruff) + format check (black) + unit tests (pytest) + schema-drift check, meant to run on PRs/feature branch pushes.

`buildspecs/buildspec-cd.yml`, on merges to this branch:
1. Vendors `pydantic` (and its compiled dependency `pydantic-core`) into each tool's deployment zip via `pip install --platform manylinux2014_x86_64 --only-binary=:all:` - the base Python 3.12 Lambda runtime doesn't include it, and this fetches the correct prebuilt wheel regardless of the CodeBuild host's own platform.
2. `aws lambda update-function-code`s each of the 3 functions.
3. Regenerates the schemas, looks up each function's real ARN (`aws lambda get-function`), and `aws ssm put-parameter --overwrite`s the tool registry with the fresh `{name, description, input_schema, lambda_arn}` catalog.

Expects `AWS_DEFAULT_REGION`, `NAME_PREFIX`, and `REGISTRY_SSM_PARAM` as CodeBuild environment variables (wired up in the `infra` branch). Every deploy writes exactly one new SSM parameter version - `aws ssm get-parameter-history --name <REGISTRY_SSM_PARAM>` shows the full history, one entry per deploy.
