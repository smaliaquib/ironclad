# Ironclad

Chat app with a streaming agent backend. Each part of the stack lives in its own branch; `master` is just this guide.

```
React + TS (frontend)  --POST /invoke-->  Go router  --POST /invoke-->  Python agent (FastAPI + Claude via Bedrock)
        <----------------------------------- SSE stream ------------------------------------------
```

## Branches

| Branch | What it is | Run |
|---|---|---|
| [`frontend`](https://github.com/smaliaquib/ironclad/tree/frontend) | React + TypeScript (Vite) chat UI, port 5173 | `npm install && npm run dev` |
| [`router`](https://github.com/smaliaquib/ironclad/tree/router) | Go service, `POST /invoke`, port 8080 | `go run .` |
| [`agent`](https://github.com/smaliaquib/ironclad/tree/agent) | FastAPI service calling Claude Haiku via AWS Bedrock, port 8000 | `uv sync && uv run uvicorn main:app --reload --port 8000` |

Each branch has its own README with full setup and config details. To run the whole stack locally, clone the three branches into sibling directories (or three worktrees of this repo) and start all three.

```
git clone --branch agent    https://github.com/smaliaquib/ironclad.git ironclad-agent
git clone --branch router   https://github.com/smaliaquib/ironclad.git ironclad-router
git clone --branch frontend https://github.com/smaliaquib/ironclad.git ironclad-frontend
```

## Docker

Each branch has its own `Dockerfile` (see that branch's README for standalone `docker build`/`docker run` usage). To run all three together, clone the three branches as above (as siblings of wherever this `master` checkout lives), create `ironclad-agent/.env` from its `.env.example`, then from this directory:

```
docker compose up --build
```

This starts agent (`:8000`), router (`:8080`), and frontend (`:5173`), wired together via `docker-compose.yml`.

## Flow

1. User types a message in the React UI.
2. Frontend POSTs `{ message }` to the router's `/invoke`.
3. Router forwards the request to the agent's `/invoke` and streams the SSE response back to the browser untouched.
4. Agent calls Claude Haiku via Bedrock with streaming enabled and emits SSE events: `token` (text delta), `done`, `error`.
