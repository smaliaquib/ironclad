# Ironclad

### *Click [here](https://drive.google.com/file/d/1ixydfVVSazi4uajdS6pnbHVO0Dk-2V6b/view) to watch video on Google Drive.*

### To see codes for applications change the github branches, also infra files are in private repo

Chat app with a streaming agent backend. Each part of the stack lives in its own branch; `master` is just this guide.

```
React + TS (frontend)  --POST /invoke-->  Go ai-gateway  --POST /invoke-->  Python agent (FastAPI + Claude via Bedrock)
        <----------------------------------- SSE stream ------------------------------------------
```


## Architecture

```
User
  │
  ▼
Route53 (only if domain_name is set)
  │
  ▼
CloudFront ── WAFv2 (managed rules + rate limit)
  │
  ├─ "/auth/*"  → Lambda@Edge (only if enable_auth) - answers directly, never
  │               reaches the ALB: sets/refreshes/clears the session cookie
  ├─ "/invoke*" → Lambda@Edge (only if enable_auth) - valid session cookie
  │               required or 401 → ALB → ai-gateway ECS Fargate service
  │                  ai-gateway: re-verifies the JWT itself, checks/records the
  │                  per-user daily token limit in DynamoDB, forwards to agent
  │                                              │
  │                                              │ Cloud Map service discovery
  │                                              │ (http://agent.<namespace>:8000)
  │                                              ▼
  │                                       agent ECS Fargate service (private, no ALB)
  │                                         ├─ bedrock-agent-runtime:Retrieve, if a
  │                                         │  knowledge base is configured (RAG - see below)
  │                                         └─ MCP over HTTP, Cloud Map DNS ──▶ mcp-gateway
  │                                            ECS Fargate service (private, no ALB) ──
  │                                            lambda:Invoke ──▶ Lambda-backed MCP tools
  ├─ "/grafana*" → passes through unconditionally → ALB → grafana ECS Fargate service
  │                  (browsed directly by a person, not called by another service)
  └─ "/", assets → passes through unconditionally → ALB → frontend ECS Fargate
                     service (the SPA always loads; it shows Login/Register
                     or Chat client-side based on a same-origin whoami check)
```

```
┌─────────────────────────────────────────── VPC 10.0.0.0/16 ────────────────────────────────────────────┐
│                                                                                                          │
│  ┌──────────────── public subnets (one per AZ, az_count = 2) ────────────────┐                          │
│  │   10.0.0.0/20, 10.0.16.0/20 - map_public_ip_on_launch = true              │                          │
│  │                                                                            │                          │
│  │   Internet Gateway          ALB (sg: alb)              NAT Gateway        │                          │
│  │        │                     0.0.0.0/0:80 or                │             │                          │
│  │        │                     CloudFront prefix list only     │             │                          │
│  │        │                     (if restrict_alb_to_cloudfront) │             │                          │
│  └────────┼─────────────────────────────┬───────────────────────┼─────────────┘                          │
│           │                             │                       │ 0.0.0.0/0 (outbound only - image       │
│           │                             │                       │ pulls, AWS API calls, Bedrock, etc.)   │
│  ┌────────┼─────────────────────────────┼───────────────────────┼─────────────────────────────────────┐  │
│  │        │   private subnets (one per AZ) - 10.0.128.0/20, 10.0.144.0/20 - no public IP                │  │
│  │        │                             │                       │                                     │  │
│  │        ▼                             ▼                       ▼                                     │  │
│  │  frontend task (sg: frontend)  ai-gateway task (sg: ai-gateway)   grafana task (sg: grafana)         │  │
│  │  ingress: alb sg only :80      ingress: alb sg only :8080         ingress: alb sg only :3000         │  │
│  │                                        │                                                             │  │
│  │                                        │ ingress: ai-gateway sg only :8000                           │  │
│  │                                        ▼                                                             │  │
│  │                                 agent task (sg: agent)                                               │  │
│  │                                        │                                                             │  │
│  │                                        │ ingress: agent sg only :8080                                │  │
│  │                                        ▼                                                             │  │
│  │                                 mcp-gateway task (sg: mcp-gateway)                                    │  │
│  │                                        │                                                             │  │
│  │  Every task security group: egress 0.0.0.0/0 (all ports/protocols), no ingress except the one rule    │  │
│  │  above - each service reachable from exactly one named source, never from the internet directly.      │  │
│  │  Private DNS namespace (Cloud Map, "<name_prefix>.local") lets agent/mcp-gateway find each other by    │  │
│  │  name without a load balancer.                                                                        │  │
│  └────────┼──────────────────────────────────────────────────────────────────────────────────────────────┘  │
└───────────┼──────────────────────────────────────────────────────────────────────────────────────────────────┘
            │ lambda:Invoke (over the AWS API, not a VPC network path)
            ▼
   12 MCP-tool Lambdas - NOT in this VPC (no vpc_config on any aws_lambda_function
   here) - they run in AWS's own Lambda-managed network, reaching Slack/Gmail/
   DuckDuckGo and SSM/KMS directly. No NAT gateway involved, no ENI cold start;
   fine since none of them need to reach anything private-subnet-only.
```
## Knowledge Base (RAG)

Drop a document into the S3 bucket and it's automatically embedded and searchable by the chat - no separate "upload" feature in the app, just S3 directly:

```
S3 documents bucket
  │  ObjectCreated:* event
  ▼
Lambda (ingestion trigger) ── bedrock:StartIngestionJob ──▶ Bedrock Knowledge Base
                                                                  │ embeds via Titan Text
                                                                  │ Embeddings v2, writes vectors
                                                                  ▼
                                                    OpenSearch Serverless collection
                                                    (VECTORSEARCH, one vector index)

agent ── bedrock-agent-runtime:Retrieve ──▶ same Knowledge Base (query only)
```
## MCP Gateway

Three pieces, each in its own branch/repo, so the pattern that already works for `frontend`/`ai-gateway`/`agent` (app code owns its own CI/CD, this repo only creates AWS resource shells) extends to the gateway and its tools too:

```
agent (LangGraph create_react_agent, langchain-aws ChatBedrockConverse)
      │  MCP over HTTP, Cloud Map DNS (MCP_GATEWAY_URL)
      ▼
mcp-gateway (ECS Fargate, Go, no ALB - private, Cloud Map only, same as agent)
  POST /mcp - hand-rolled JSON-RPC 2.0: initialize / tools/list / tools/call
      │
      │ tools/list → reads the tool registry (SSM Parameter, cached ~60s)
      │ tools/call → lambda:Invoke on the ARN the registry names for that tool
      ▼
Lambda: mcp-tool-echo / mcp-tool-get_time / mcp-tool-add_numbers (dummy tools)
        mcp-tool-slack_post_message / mcp-tool-slack_read_history / mcp-tool-slack_list_channels
        mcp-tool-gmail_search / mcp-tool-gmail_read / mcp-tool-gmail_send / mcp-tool-gmail_reply
        mcp-tool-duckduckgo_search / mcp-tool-duckduckgo_fetch
```

## Branches

| Branch | What it is | Run |
|---|---|---|
| [`frontend`](https://github.com/smaliaquib/ironclad/tree/frontend) | React + TypeScript (Vite) chat UI, port 5173 | `npm install && npm run dev` |
| [`ai-gateway`](https://github.com/smaliaquib/ironclad/tree/ai-gateway) | Go service, `POST /invoke`, port 8080 (formerly `router`) | `go run .` |
| [`agent`](https://github.com/smaliaquib/ironclad/tree/agent) | FastAPI service calling Claude Haiku via AWS Bedrock, port 8000 | `uv sync && uv run uvicorn main:app --reload --port 8000` |

Terraform for the AWS deployment lives in a separate **private** repo (`ironclad-infra`), not a branch here — see [AWS deployment](#aws-deployment) below. Everyone else's app code is public; only the infra (account IDs, resource layout) is kept private.


```
git clone --branch master https://github.com/smaliaquib/ironclad.git ironclad
cd ironclad
git worktree add ../frontend    frontend
git worktree add ../ai-gateway  ai-gateway
git worktree add ../agent       agent
```

This gives you sibling folders `frontend/`, `ai-gateway/`, `agent/` next to this `ironclad/` (master) checkout — `cd` into whichever one you're working on, no branch switching required. `git worktree list` shows all of them; `git worktree remove <path>` drops one you no longer need.

The infra repo isn't part of this worktree set (it's a separate GitHub repo, not a branch of this one) — clone it on its own if you have access: `git clone https://github.com/smaliaquib/ironclad-infra.git`.

## Docker

Each branch has its own `Dockerfile` (see that branch's README for standalone `docker build`/`docker run` usage). To run all three together, set up the worktrees as above, create `agent/.env` from its `.env.example`, then from this directory:

```
docker compose up --build
```

This starts agent (`:8000`), ai-gateway (`:8080`), and frontend (`:5173`), wired together via `docker-compose.yml`.

## AWS deployment

Terraform for running this on ECS Fargate lives in the private [`ironclad-infra`](https://github.com/smaliaquib/ironclad-infra) repo (access on request) rather than a branch of this repo: one public ALB path-routes to frontend (`/`) and ai-gateway (`/invoke*`); agent has no ALB and is reached from ai-gateway over Cloud Map service discovery. Each app is its own ECS service, ECR repo, CloudWatch log group, and CodePipeline tracking its own branch. See that repo's README before running `terraform apply`.

## Flow

1. User types a message in the React UI.
2. Frontend POSTs `{ message }` to ai-gateway's `/invoke`.
3. ai-gateway forwards the request to the agent's `/invoke` and streams the SSE response back to the browser untouched.
4. Agent calls Claude Haiku via Bedrock with streaming enabled and emits SSE events: `token` (text delta), `done`, `error`.
