# Ironclad

Chat app with a streaming agent backend. Each part of the stack lives in its own branch; `master` is just this guide.

```
React + TS (frontend)  --POST /invoke-->  Go ai-gateway  --POST /invoke-->  Python agent (FastAPI + Claude via Bedrock)
        <----------------------------------- SSE stream ------------------------------------------
```

## Branches

| Branch | What it is | Run |
|---|---|---|
| [`frontend`](https://github.com/smaliaquib/ironclad/tree/frontend) | React + TypeScript (Vite) chat UI, port 5173 | `npm install && npm run dev` |
| [`ai-gateway`](https://github.com/smaliaquib/ironclad/tree/ai-gateway) | Go service, `POST /invoke`, port 8080 (formerly `router`) | `go run .` |
| [`agent`](https://github.com/smaliaquib/ironclad/tree/agent) | FastAPI service calling Claude Haiku via AWS Bedrock, port 8000 | `uv sync && uv run uvicorn main:app --reload --port 8000` |
| [`infra`](https://github.com/smaliaquib/ironclad/tree/infra) | Terraform: AWS ECS Fargate + single ALB + CodePipeline per app | `terraform init && terraform plan -var-file=envs/dev.tfvars` |

Each branch has its own README with full setup and config details. Working across all four at once (without repeatedly `git checkout`ing back and forth) is exactly what [git worktrees](https://git-scm.com/docs/git-worktree) are for — one clone, one `.git`, but each branch checked out into its own folder simultaneously:

```
git clone --branch master https://github.com/smaliaquib/ironclad.git ironclad
cd ironclad
git worktree add ../frontend    frontend
git worktree add ../ai-gateway  ai-gateway
git worktree add ../agent       agent
git worktree add ../infra       infra
```

This gives you sibling folders `frontend/`, `ai-gateway/`, `agent/`, `infra/` next to this `ironclad/` (master) checkout — `cd` into whichever one you're working on, no branch switching required. `git worktree list` shows all of them; `git worktree remove <path>` drops one you no longer need.

## Docker

Each branch has its own `Dockerfile` (see that branch's README for standalone `docker build`/`docker run` usage). To run all three together, set up the worktrees as above, create `agent/.env` from its `.env.example`, then from this directory:

```
docker compose up --build
```

This starts agent (`:8000`), ai-gateway (`:8080`), and frontend (`:5173`), wired together via `docker-compose.yml`.

## AWS deployment

The `infra` branch has Terraform for running this on ECS Fargate: one public ALB path-routes to frontend (`/`) and ai-gateway (`/invoke*`); agent has no ALB and is reached from ai-gateway over Cloud Map service discovery. Each app is its own ECS service, ECR repo, CloudWatch log group, and CodePipeline tracking its own branch. Nothing has been applied yet — see that branch's README before running `terraform apply`.

## Flow

1. User types a message in the React UI.
2. Frontend POSTs `{ message }` to ai-gateway's `/invoke`.
3. ai-gateway forwards the request to the agent's `/invoke` and streams the SSE response back to the browser untouched.
4. Agent calls Claude Haiku via Bedrock with streaming enabled and emits SSE events: `token` (text delta), `done`, `error`.
