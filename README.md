
# Ironclad — router

The router service for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview and how this fits with the `agent` and `frontend` branches.

Go service that exposes `POST /invoke`, forwards the request to the agent service, and streams the SSE response straight through to the caller.

## Run

```
go run .
```

## Config (env vars)

- `AGENT_URL` — base URL of the agent service (default `http://localhost:8000`)
- `ROUTER_ADDR` — listen address (default `:8080`)

### Docker

```
docker build -t ironclad-router .
docker run --rm -p 8080:8080 -e AGENT_URL=http://host.docker.internal:8000 ironclad-router
```

## API

`POST /invoke` — body `{ "message": string }`, proxies to the agent and streams back `text/event-stream` unchanged.

`GET /health` — liveness check.

## Lint, format, test

```
gofmt -l .          # lists any unformatted files (empty output = clean)
go vet ./...
go test ./... -v
```

## CI/CD

`buildspecs/buildspec-ci.yml` — gofmt check + `go vet` + `go test`, meant to run on PRs/feature branch pushes.

`buildspecs/buildspec-cd.yml` — builds the Docker image, pushes `:latest` and `:<commit-sha>` to ECR, then forces an ECS redeployment (`aws ecs update-service --force-new-deployment`) on merges to this branch. Expects `ECR_REPO_URL`, `AWS_DEFAULT_REGION`, `AWS_ACCOUNT_ID`, `ECS_CLUSTER`, `ECS_SERVICE` as CodeBuild environment variables (wired up in the `infra` branch).
