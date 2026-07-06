
# Ironclad — agent

The agent service for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview and how this fits with the `ai-gateway` and `frontend` branches.

FastAPI service running a [LangGraph](https://github.com/langchain-ai/langgraph) tool-calling agent (Claude Haiku via AWS Bedrock, `langchain-aws`'s `ChatBedrockConverse`) and streaming the response back as SSE. Dependency management is via [uv](https://github.com/astral-sh/uv).

## Run

```
uv sync
copy .env.example .env   # adjust AWS_REGION / BEDROCK_MODEL_ID, set AWS creds if not using the default chain
uv run uvicorn main:app --reload --port 8000
```

AWS credentials come from the standard chain (env vars, `~/.aws/credentials`, profile, or instance/task role) — no Anthropic API key needed.

Optional `KNOWLEDGE_BASE_SSM_PARAM` env var enables RAG: if set, the knowledge base id is fetched once at startup from that SSM parameter (`ssm:GetParameter`) - not baked in directly, so the knowledge base can be recreated without needing a new deployment - and every message then calls Bedrock's `Retrieve` API against it, weaving any matching chunks into the prompt before the normal Claude call. Unset (the default) skips retrieval entirely, so this needs no extra setup for local dev. A failed SSM lookup (missing parameter, no permission) logs a warning and falls back to no-RAG rather than crashing the service.

Optional `MCP_GATEWAY_URL` env var enables tool use: if set, `mcp_tools.py` fetches the current tool catalog from `<url>/mcp` (`tools/list`, cached ~60s) and wraps each entry as a LangGraph `StructuredTool` whose call goes back through the same endpoint (`tools/call`) - see the [`mcp-gateway`](https://github.com/smaliaquib/ironclad/tree/mcp-gateway)/[`mcp-tools`](https://github.com/smaliaquib/ironclad/tree/mcp-tools) branches for what's actually running behind it. Unset (the default) runs the agent with no tools at all - same graceful-degradation shape as the knowledge base. A tool call that fails (bad arguments, the tool's Lambda erroring, the gateway being unreachable) surfaces back to the model as a failed tool call, not a crashed request.

Uses `langgraph.prebuilt.create_react_agent` rather than the newer `langchain.agents.create_agent` - deliberately, because the newer API doesn't yet propagate token-level streaming events through `astream_events` (verified directly; the deprecated one does), and real token streaming is a hard requirement here. Revisit once that catches up.

Runs with a fixed system prompt (`main.py`'s `SYSTEM_PROMPT`) establishing it as a general-purpose assistant. Conversation memory is stateless on this service by design: the caller (ai-gateway/frontend) resends the full prior conversation as `history` on every `/invoke` call rather than this service tracking sessions itself - there's no thread-id, no checkpointer, no new datastore. History is capped to the most recent `MAX_HISTORY_MESSAGES` turns (oldest dropped first) so token usage/cost don't grow unbounded as a conversation gets long.

### Docker

```
docker build -t ironclad-agent .
docker run --rm -p 8000:8000 --env-file .env ironclad-agent
```

Or pass AWS credentials directly: `-e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... -e AWS_REGION=us-east-1`.

## API

`POST /invoke` — body `{ "message": string, "history"?: { role: "user" | "assistant", content: string }[] }` (`history` is the prior turns of this conversation, oldest first, not including `message` itself), responds with `text/event-stream`:

- `event: sources` — `{ "sources": string[] }`, source document filenames - only sent if a knowledge base is configured and retrieval returned matches, always before any `token` events
- `event: token` — `{ "text": string }` delta
- `event: usage` — `{ "input_tokens": number, "output_tokens": number, "model_id": string, "tool_calls": number }`, real Bedrock token counts summed across every model call the tool-use loop made this turn (a tool-calling exchange makes more than one) - ai-gateway (not this service) uses this to enforce per-user daily limits and to emit its own per-request usage/cost/latency metrics (see the `ai-gateway` branch's README)
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

`buildspecs/buildspec-cd.yml` — builds the Docker image, pushes `:latest` and `:<commit-sha>` to ECR, then forces an ECS redeployment (`aws ecs update-service --force-new-deployment`) on merges to this branch. Expects `ECR_REPO_URL`, `AWS_DEFAULT_REGION`, `AWS_ACCOUNT_ID`, `ECS_CLUSTER`, `ECS_SERVICE` as CodeBuild environment variables (wired up in the private `ironclad-infra` repo).
