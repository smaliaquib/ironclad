
# Ironclad — agent

The agent service for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview and how this fits with the `router` and `frontend` branches.

FastAPI service that calls Claude Haiku through AWS Bedrock and streams the response back as SSE. Dependency management is via [uv](https://github.com/astral-sh/uv).

## Run

```
uv sync
copy .env.example .env   # adjust AWS_REGION / BEDROCK_MODEL_ID, set AWS creds if not using the default chain
uv run uvicorn main:app --reload --port 8000
```

AWS credentials come from the standard chain (env vars, `~/.aws/credentials`, profile, or instance/task role) — no Anthropic API key needed.

Optional `KNOWLEDGE_BASE_SSM_PARAM` env var enables RAG: if set, the knowledge base id is fetched once at startup from that SSM parameter (`ssm:GetParameter`) - not baked in directly, so the knowledge base can be recreated without needing a new deployment - and every message then calls Bedrock's `Retrieve` API against it, weaving any matching chunks into the prompt before the normal Claude call. Unset (the default) skips retrieval entirely, so this needs no extra setup for local dev. A failed SSM lookup (missing parameter, no permission) logs a warning and falls back to no-RAG rather than crashing the service.

### Docker

```
docker build -t ironclad-agent .
docker run --rm -p 8000:8000 --env-file .env ironclad-agent
```

Or pass AWS credentials directly: `-e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... -e AWS_REGION=us-east-1`.

## API

`POST /invoke` — body `{ "message": string }`, responds with `text/event-stream`:

- `event: sources` — `{ "sources": string[] }`, source document filenames - only sent if a knowledge base is configured and retrieval returned matches, always before any `token` events
- `event: token` — `{ "text": string }` delta
- `event: usage` — `{ "input_tokens": number, "output_tokens": number }`, real Bedrock token counts - the router (not this service) uses this to enforce per-user daily limits
- `event: done` — stream finished
- `event: error` — `{ "message": string }`

`GET /health` — liveness check.

## Lint, format, test

```
uv sync --frozen
uv run ruff check .
uv run black --check .
uv run pytest tests/unit/ -v
```

## CI/CD

`buildspecs/buildspec-ci.yml` — lint (ruff) + format check (black) + unit tests (pytest), meant to run on PRs/feature branch pushes.

`buildspecs/buildspec-cd.yml` — builds the Docker image, pushes `:latest` and `:<commit-sha>` to ECR, then forces an ECS redeployment (`aws ecs update-service --force-new-deployment`) on merges to this branch. Expects `ECR_REPO_URL`, `AWS_DEFAULT_REGION`, `AWS_ACCOUNT_ID`, `ECS_CLUSTER`, `ECS_SERVICE` as CodeBuild environment variables (wired up in the `infra` branch).
