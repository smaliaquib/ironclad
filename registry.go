package main

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/ssm"
)

// Tool is one entry in the tool registry - published by the mcp-tools
// application's own CD pipeline as a JSON array stored in an SSM Parameter.
// input_schema is generated from that tool's Pydantic model, never hand
// written, so it can never drift from what the Lambda actually validates.
type Tool struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	InputSchema json.RawMessage `json:"input_schema"`
	LambdaARN   string          `json:"lambda_arn"`
}

// ssmGetParameterAPI is the one method this file needs from *ssm.Client -
// narrowed to an interface so tests can substitute a fake without a real
// AWS client or network access.
type ssmGetParameterAPI interface {
	GetParameter(ctx context.Context, params *ssm.GetParameterInput, optFns ...func(*ssm.Options)) (*ssm.GetParameterOutput, error)
}

const registryCacheTTL = 60 * time.Second

type registryCache struct {
	mu        sync.Mutex
	tools     []Tool
	fetchedAt time.Time
}

var cache registryCache

// loadRegistry returns the current tool catalog, refreshing it from SSM at
// most once per registryCacheTTL. Deploys to mcp-tools write a new SSM
// parameter version, so the gateway picks up new/changed tools within one
// TTL window without needing a restart. versionLabel, if set, pins the
// gateway to a specific labeled version (aws ssm label-parameter-version)
// instead of always reading the latest.
func loadRegistry(ctx context.Context, client ssmGetParameterAPI, paramName, versionLabel string) ([]Tool, error) {
	cache.mu.Lock()
	defer cache.mu.Unlock()

	if cache.tools != nil && time.Since(cache.fetchedAt) < registryCacheTTL {
		return cache.tools, nil
	}

	name := paramName
	if versionLabel != "" {
		name = fmt.Sprintf("%s:%s", paramName, versionLabel)
	}

	out, err := client.GetParameter(ctx, &ssm.GetParameterInput{Name: aws.String(name)})
	if err != nil {
		return nil, fmt.Errorf("fetching registry parameter %s: %w", name, err)
	}

	var tools []Tool
	if err := json.Unmarshal([]byte(aws.ToString(out.Parameter.Value)), &tools); err != nil {
		return nil, fmt.Errorf("parsing registry parameter %s: %w", name, err)
	}

	cache.tools = tools
	cache.fetchedAt = time.Now()
	return tools, nil
}

func findTool(tools []Tool, name string) (Tool, bool) {
	for _, t := range tools {
		if t.Name == name {
			return t, true
		}
	}
	return Tool{}, false
}
