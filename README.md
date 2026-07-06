
# Ironclad — grafana

Observability for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview. This is a stock [`grafana/grafana-oss`](https://hub.docker.com/r/grafana/grafana-oss) image, configured entirely through provisioning files (datasource + dashboards) baked into the Docker image — there's no custom application code in this branch, no database to persist state in, and no in-UI dashboard editing (`allowUiUpdates: false`) - dashboards are edited here, in git, not in a running Grafana instance.

## What it shows

The `ai-gateway` branch emits one structured [CloudWatch Embedded Metric Format](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html) (EMF) log line per completed `/invoke` request — the same line is both a real CloudWatch custom metric (namespace `Ironclad/Usage`, dimensioned by `Model`/`Status` only) and a fully queryable Logs Insights record (with `user_id` as a flat field, not a metric dimension — no cardinality cost as the user base grows). Three dashboards, all reading from CloudWatch directly (no Prometheus, no OpenTelemetry collector):

- **Usage Overview** (`dashboards/usage-overview.json`) — requests/tokens/cost over time, from CloudWatch Metrics.
- **Per-User Usage** (`dashboards/per-user-usage.json`) — a table (tokens used, cost, avg latency, daily limit/remaining) grouped by `user_id`, from a CloudWatch **Logs Insights** query against `/ecs/ironclad-dev-ai-gateway`.
- **Latency & Errors** (`dashboards/latency-errors.json`) — p50/p95/p99 latency and request counts by status (`success`/`error`/`rate_limited`).

**Verified live against a real deployed instance (via `curl -u admin:<password> .../api/ds/query`, bypassing the need for a browser).** Two real bugs found and fixed this way:
1. Every panel/target needs an explicit `"datasource": {"type": "cloudwatch", "uid": "cloudwatch"}` — omitting the `uid` (only `type`) fails outright with `"Query does not contain a valid data source identifier"`, even though the API happily infers it when you pass a bare `{"type": "cloudwatch"}` directly to `/api/ds/query` yourself. `provisioning/datasources/cloudwatch.yaml` pins a fixed `uid: cloudwatch` (not Grafana's auto-generated random hash) so this stays stable across container restarts — there's no persistent volume here, so a fresh restart re-runs provisioning from scratch.
2. The Logs Insights query (`per-user-usage.json`) needs the log group's **ARN**, not just its name (`"LogGroup cannot be empty"` otherwise) — `arn:aws:logs:<region>:<account-id>:log-group:/ecs/ironclad-dev-ai-gateway:*` is baked in, so it's specific to this AWS account; update it if you fork this into a different account.

## Cost/pricing numbers

The `CostUsd` metric comes from `ai-gateway/pricing.go`'s hardcoded model-pricing table, not a live AWS pricing API (Bedrock doesn't have one) — treat cost figures as an estimate, and verify the per-model rates against the [Bedrock pricing page](https://aws.aws.amazon.com/bedrock/pricing/) for your region periodically.

## Admin access

`GF_SECURITY_ADMIN_PASSWORD` is fetched from SSM (SecureString) by `entrypoint.sh` at container startup (`aws ssm get-parameter --with-decryption`), never baked into the image or committed anywhere. The private `ironclad-infra` repo's `modules/grafana` creates the SSM parameter shell only (`lifecycle { ignore_changes = [value] }`, same pattern as the Slack/Gmail credentials) — set the real password once after `terraform apply`:

```
aws ssm put-parameter --name <grafana_admin_password_ssm_parameter_name output> --type SecureString --value '<a real password>' --overwrite
```

Reachable at `https://<your CloudFront domain>/grafana/` once deployed (path-routed through the same ALB/CloudFront distribution as `frontend`/`ai-gateway`).

## Run locally

```
docker build -t ironclad-grafana .
docker run --rm -p 3000:3000 -e AWS_REGION=us-east-1 -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... ironclad-grafana
```

Without `GRAFANA_ADMIN_PASSWORD_SSM_PARAM` set, `entrypoint.sh` skips the SSM fetch entirely and falls back to Grafana's own default (`admin`/`admin`) — fine for local poking around, not for anything real. The CloudWatch datasource needs real AWS credentials with read access to CloudWatch Metrics/Logs Insights to show any data locally.

## CI/CD

`buildspecs/buildspec-ci.yml` — validates every `dashboards/*.json` file is well-formed JSON, then confirms the image actually builds. No app-level tests (there's no application code) - meant to run on PRs/feature branch pushes.

`buildspecs/buildspec-cd.yml` — builds the image, pushes `:latest` and `:<commit-sha>` to ECR, then forces an ECS redeployment on merges to this branch. Expects `ECR_REPO_URL`, `AWS_DEFAULT_REGION`, `AWS_ACCOUNT_ID`, `ECS_CLUSTER`, `ECS_SERVICE` as CodeBuild environment variables (wired up in the private `ironclad-infra` repo) — identical shape to `ai-gateway`'s CD, since this is a plain ECS Fargate service like every other app here.
