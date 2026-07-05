
# Ironclad — mcp-gateway

The MCP gateway service for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview. Go service exposing a thin JSON-RPC 2.0 (MCP wire protocol) endpoint that dispatches tool calls to Lambda functions - it has no tool-specific logic of its own; every tool comes from the registry.

```
agent (future: tool-use loop) --POST /mcp--> mcp-gateway --lambda:Invoke--> mcp-tools' Lambdas
```

## Run

```
go run .
```

## Config (env vars)

- `MCP_GATEWAY_ADDR` — listen address (default `:9000`)
- `AWS_REGION` — region for the SSM/Lambda clients (default `us-east-1`)
- `MCP_REGISTRY_SSM_PARAM` — SSM parameter name holding the tool registry (JSON array of `{name, description, input_schema, lambda_arn}`), written by the `mcp-tools` branch's own CD pipeline
- `MCP_REGISTRY_VERSION_LABEL` — optional; if set, reads a specific labeled parameter version (`aws ssm label-parameter-version`) instead of always the latest, for pinning the served catalog independent of the newest deploy

### Docker

```
docker build -t ironclad-mcp-gateway .
docker run --rm -p 9000:9000 -e MCP_REGISTRY_SSM_PARAM=/ironclad-dev/mcp-gateway/tool-registry ironclad-mcp-gateway
```

## API

`POST /mcp` — hand-rolled JSON-RPC 2.0, methods:

- `initialize` → `{ protocolVersion, serverInfo }`
- `tools/list` → `{ tools: [{ name, description, inputSchema }] }`, read from the tool registry (cached in memory, refreshed at most once every 60s so a new `mcp-tools` deploy is picked up without a gateway restart)
- `tools/call` → `{ name, arguments }` in, `{ content: [{ type: "text", text }], isError? }` out. Invokes the tool's Lambda synchronously; a Lambda-side `FunctionError` maps to `isError: true` rather than an HTTP 5xx.

`GET /health` — liveness check.

`GET /openapi.yaml` — static OpenAPI 3.0 doc describing this gateway's own two endpoints (the gateway has no per-tool business logic to generate docs from - the tools' own schemas are what `tools/list` returns).

## Lint, format, test

```
gofmt -l .          # lists any unformatted files (empty output = clean)
go vet ./...
go test ./... -v
```

## CI/CD

`buildspecs/buildspec-ci.yml` — gofmt check + `go vet` + `go test`, meant to run on PRs/feature branch pushes.

`buildspecs/buildspec-cd.yml` — builds the Docker image, pushes `:latest` and `:<commit-sha>` to ECR, then forces an ECS redeployment (`aws ecs update-service --force-new-deployment`) on merges to this branch. Expects `ECR_REPO_URL`, `AWS_DEFAULT_REGION`, `AWS_ACCOUNT_ID`, `ECS_CLUSTER`, `ECS_SERVICE` as CodeBuild environment variables (wired up in the `infra` branch).
