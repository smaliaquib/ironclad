# Ironclad — ai-gateway

The AI gateway service for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview and how this fits with the `agent` and `frontend` branches. (Formerly named `router`.)

Go service that exposes `POST /invoke`, forwards the request to the agent service, and streams the SSE response straight through to the caller.

## Run

```
go run .
```

## Config (env vars)

- `AGENT_URL` — base URL of the agent service (default `http://localhost:8000`)
- `AI_GATEWAY_ADDR` — listen address (default `:8080`)
- `REQUIRE_AUTH` — when `true`, `/invoke` requires a valid Cognito `id_token` cookie (re-verified here against Cognito's JWKS, independent of whatever CloudFront's Lambda@Edge already checked) and enforces the per-user daily token limit. Defaults off, so local dev needs no Cognito setup at all.
- `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `AWS_REGION` — required when `REQUIRE_AUTH=true`, used to verify the JWT (issuer/audience) and fetch its JWKS.
- `USAGE_TABLE_NAME`, `DAILY_TOKEN_LIMIT` — required when `REQUIRE_AUTH=true`: the DynamoDB table tracking each user's daily Bedrock token usage, and the cap (tokens/user/UTC day) before `/invoke` starts returning `429`. ai-gateway watches the agent's SSE stream for a `usage` event to record actual usage after each request.

## Observability

Every completed `/invoke` request (success, error, or rate-limited) emits one structured [CloudWatch Embedded Metric Format](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html) JSON line to stdout (`metrics.go`'s `emitUsageMetric`, via `fmt.Println` — not `log.Println`, which would prepend a timestamp and break CloudWatch's auto-detection of the `_aws` block). CloudWatch Logs auto-parses that block into real custom metrics (namespace `Ironclad/Usage`, dimensioned by `Model`+`Status` only — bounded, cheap), while the *same* line stays fully queryable via Logs Insights, with `user_id` as a flat field for per-user breakdowns (deliberately not a metric dimension — no cardinality cost as the user base grows). See the `grafana` branch for the dashboards built on top of this.

`pricing.go`'s `modelPricing` map is a manually-maintained table (Bedrock has no live pricing API) used to estimate `CostUsd` — verify the per-model rates against the [Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) for your region, and add an entry whenever `BEDROCK_MODEL_ID` changes to something not already in the table (unknown models report $0 cost with a logged warning, not a crash).

### Docker

```
docker build -t ironclad-ai-gateway .
docker run --rm -p 8080:8080 -e AGENT_URL=http://host.docker.internal:8000 ironclad-ai-gateway
```

## API

`POST /invoke` — body `{ "message": string }`, proxies to the agent and streams back `text/event-stream` unchanged. Returns `401` if `REQUIRE_AUTH` is on and the `id_token` cookie is missing/invalid, or `429` if the caller is already at today's token limit.

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
