# Ironclad

Chat app with a streaming agent backend.

```
React + TS (frontend)  --POST /invoke-->  Go router  --POST /invoke-->  Python agent (FastAPI + Claude via Bedrock)
        <----------------------------------- SSE stream ------------------------------------------
```

## Services

### agent/ (Python, port 8000)

Uses [uv](https://github.com/astral-sh/uv) for dependency management and calls Claude Haiku through AWS Bedrock (`AsyncAnthropicBedrock`), so credentials come from the standard AWS chain (env vars, `~/.aws/credentials`, profile, or instance/task role) rather than an Anthropic API key.

```
cd agent
uv sync
copy .env.example .env   # adjust AWS_REGION / BEDROCK_MODEL_ID, set AWS creds if not using the default chain
uv run uvicorn main:app --reload --port 8000
```

### router/ (Go, port 8080)

```
cd router
go run .
```

Set `AGENT_URL` if the agent isn't at `http://localhost:8000` (default), or `ROUTER_ADDR` to change its listen address (default `:8080`).

### frontend/ (React + TS via Vite, port 5173)

```
cd frontend
copy .env.example .env   # optional, defaults to http://localhost:8080
npm install
npm run dev
```

## Flow

1. User types a message in the React UI.
2. Frontend POSTs `{ message }` to the router's `/invoke`.
3. Router forwards the request to the agent's `/invoke` and streams the SSE response back to the browser untouched.
4. Agent calls Claude Haiku via Bedrock with streaming enabled and emits SSE events: `token` (text delta), `done`, `error`.
