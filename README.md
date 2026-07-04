# Ironclad — frontend

The frontend for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview and how this fits with the `router` and `agent` branches.

React + TypeScript (Vite) chat UI that streams responses from the router via SSE.

## Run

```
copy .env.example .env   # optional, defaults to http://localhost:8080
npm install
npm run dev
```

## Config (env vars)

- `VITE_ROUTER_URL` — base URL of the router service. Empty (the default) means "same origin, relative `/invoke`" — correct in production, where a gateway (ALB or CloudFront) path-routes `/invoke*` to the router on the same hostname as the frontend. Only set this to an absolute URL for local dev / docker-compose, where frontend and router run on different origins (`.env.example` sets `http://localhost:8080` for exactly that reason).

## Build

```
npm run build
```

### Docker

`VITE_ROUTER_URL` is baked in at build time (Vite env vars are compile-time). Leave it unset for a production-style image (relative `/invoke`), or pass it as a build arg for standalone local testing where the router isn't behind the same origin:

```
docker build -t ironclad-frontend --build-arg VITE_ROUTER_URL=http://localhost:8080 .
docker run --rm -p 5173:80 ironclad-frontend
```

Serves the built app via nginx with SPA fallback routing.

## Lint, format, test

```
npm run lint          # eslint
npm run format:check  # prettier --check
npx tsc --noEmit       # typecheck
npm run test           # vitest run
```

## CI/CD

`buildspecs/buildspec-ci.yml` — eslint + prettier check + typecheck + vitest, meant to run on PRs/feature branch pushes.

`buildspecs/buildspec-cd.yml` — builds the Docker image (no `VITE_ROUTER_URL` build arg, so it defaults to empty/relative), pushes `:latest` and `:<commit-sha>` to ECR, then forces an ECS redeployment (`aws ecs update-service --force-new-deployment`) on merges to this branch. Expects `ECR_REPO_URL`, `AWS_DEFAULT_REGION`, `AWS_ACCOUNT_ID`, `ECS_CLUSTER`, `ECS_SERVICE` as CodeBuild environment variables (wired up in the `infra` branch).
