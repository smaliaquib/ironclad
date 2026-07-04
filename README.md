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

## API

`POST /invoke` — body `{ "message": string }`, responds with `text/event-stream`:

- `event: token` — `{ "text": string }` delta
- `event: done` — stream finished
- `event: error` — `{ "message": string }`

`GET /health` — liveness check.
