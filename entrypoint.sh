#!/bin/sh
set -e

# GRAFANA_ADMIN_PASSWORD_SSM_PARAM unset (local dev / docker-compose without
# real AWS access) - skip the SSM fetch entirely and fall back to whatever
# GF_SECURITY_ADMIN_PASSWORD is already set to (Grafana's own "admin"
# default if that's unset too). Same graceful-degradation shape as the
# agent's KNOWLEDGE_BASE_SSM_PARAM/MCP_GATEWAY_URL.
if [ -n "$GRAFANA_ADMIN_PASSWORD_SSM_PARAM" ]; then
  export GF_SECURITY_ADMIN_PASSWORD="$(aws ssm get-parameter \
    --name "$GRAFANA_ADMIN_PASSWORD_SSM_PARAM" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text \
    --region "${AWS_REGION:-us-east-1}")"
fi

exec /run.sh
