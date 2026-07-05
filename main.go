package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/lambda"
	"github.com/aws/aws-sdk-go-v2/service/lambda/types"
	"github.com/aws/aws-sdk-go-v2/service/ssm"
)

// lambdaInvokeAPI is the one method this file needs from *lambda.Client -
// narrowed to an interface so tests can substitute a fake.
type lambdaInvokeAPI interface {
	Invoke(ctx context.Context, params *lambda.InvokeInput, optFns ...func(*lambda.Options)) (*lambda.InvokeOutput, error)
}

var (
	ssmClient            ssmGetParameterAPI
	lambdaClient         lambdaInvokeAPI
	registryParamName    string
	registryVersionLabel string
)

// Hand-rolled JSON-RPC 2.0 (the MCP wire protocol) rather than an SDK -
// initialize/tools/list/tools/call is small and stable enough to implement
// directly, with zero dependency on an MCP SDK's internal API shape.
type rpcRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type rpcResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Result  any             `json:"result,omitempty"`
	Error   *rpcError       `json:"error,omitempty"`
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

const (
	rpcParseError     = -32700
	rpcInvalidParams  = -32602
	rpcMethodNotFound = -32601
	rpcInternalError  = -32000
)

type toolListItem struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	InputSchema json.RawMessage `json:"inputSchema"`
}

type toolCallParams struct {
	Name      string          `json:"name"`
	Arguments json.RawMessage `json:"arguments"`
}

type toolContent struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type toolCallResult struct {
	Content []toolContent `json:"content"`
	IsError bool          `json:"isError,omitempty"`
}

func main() {
	registryParamName = os.Getenv("MCP_REGISTRY_SSM_PARAM")
	registryVersionLabel = os.Getenv("MCP_REGISTRY_VERSION_LABEL")

	region := os.Getenv("AWS_REGION")
	if region == "" {
		region = "us-east-1"
	}

	cfg, err := config.LoadDefaultConfig(context.Background(), config.WithRegion(region))
	if err != nil {
		log.Fatalf("aws config load failed: %v", err)
	}
	ssmClient = ssm.NewFromConfig(cfg)
	lambdaClient = lambda.NewFromConfig(cfg)

	addr := os.Getenv("MCP_GATEWAY_ADDR")
	if addr == "" {
		addr = ":9000"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/mcp", handleMCP)
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/openapi.yaml", handleOpenAPI)

	log.Printf("mcp-gateway listening on %s, registry param %s", addr, registryParamName)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Write([]byte(`{"status":"ok"}`))
}

func handleMCP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req rpcRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeRPCError(w, nil, rpcParseError, "parse error")
		return
	}

	switch req.Method {
	case "initialize":
		writeRPCResult(w, req.ID, map[string]any{
			"protocolVersion": "2025-06-18",
			"serverInfo":      map[string]string{"name": "ironclad-mcp-gateway", "version": "0.1.0"},
		})

	case "tools/list":
		tools, err := loadRegistry(r.Context(), ssmClient, registryParamName, registryVersionLabel)
		if err != nil {
			writeRPCError(w, req.ID, rpcInternalError, err.Error())
			return
		}
		items := make([]toolListItem, 0, len(tools))
		for _, t := range tools {
			items = append(items, toolListItem{Name: t.Name, Description: t.Description, InputSchema: t.InputSchema})
		}
		writeRPCResult(w, req.ID, map[string]any{"tools": items})

	case "tools/call":
		var params toolCallParams
		if len(req.Params) == 0 || json.Unmarshal(req.Params, &params) != nil || params.Name == "" {
			writeRPCError(w, req.ID, rpcInvalidParams, "invalid params: expected {name, arguments}")
			return
		}

		tools, err := loadRegistry(r.Context(), ssmClient, registryParamName, registryVersionLabel)
		if err != nil {
			writeRPCError(w, req.ID, rpcInternalError, err.Error())
			return
		}
		tool, ok := findTool(tools, params.Name)
		if !ok {
			writeRPCError(w, req.ID, rpcMethodNotFound, fmt.Sprintf("unknown tool: %s", params.Name))
			return
		}

		writeRPCResult(w, req.ID, callTool(r.Context(), lambdaClient, tool, params.Arguments))

	default:
		writeRPCError(w, req.ID, rpcMethodNotFound, fmt.Sprintf("method not found: %s", req.Method))
	}
}

// callTool invokes the tool's Lambda synchronously and maps a Lambda-side
// FunctionError to an MCP-shaped isError result instead of a 5xx - the
// caller (a future agent tool-use loop) sees a normal tool_result either way.
func callTool(ctx context.Context, client lambdaInvokeAPI, tool Tool, arguments json.RawMessage) toolCallResult {
	payload := arguments
	if len(payload) == 0 {
		payload = []byte("{}")
	}

	out, err := client.Invoke(ctx, &lambda.InvokeInput{
		FunctionName:   aws.String(tool.LambdaARN),
		InvocationType: types.InvocationTypeRequestResponse,
		Payload:        payload,
	})
	if err != nil {
		return errorResult(fmt.Sprintf("invoking %s: %v", tool.Name, err))
	}
	if out.FunctionError != nil {
		return errorResult(fmt.Sprintf("%s returned an error: %s", tool.Name, string(out.Payload)))
	}
	return toolCallResult{Content: []toolContent{{Type: "text", Text: string(out.Payload)}}}
}

func errorResult(message string) toolCallResult {
	return toolCallResult{Content: []toolContent{{Type: "text", Text: message}}, IsError: true}
}

func writeRPCResult(w http.ResponseWriter, id json.RawMessage, result any) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(rpcResponse{JSONRPC: "2.0", ID: id, Result: result})
}

func writeRPCError(w http.ResponseWriter, id json.RawMessage, code int, message string) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(rpcResponse{JSONRPC: "2.0", ID: id, Error: &rpcError{Code: code, Message: message}})
}
