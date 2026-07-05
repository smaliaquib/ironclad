package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/lambda"
	"github.com/aws/aws-sdk-go-v2/service/ssm"
	ssmtypes "github.com/aws/aws-sdk-go-v2/service/ssm/types"
)

const testRegistryJSON = `[
  {"name":"echo","description":"Echoes back a message.","input_schema":{"type":"object"},"lambda_arn":"arn:aws:lambda:us-east-1:123:function:echo"}
]`

type fakeSSMClient struct {
	value string
	err   error
}

func (f *fakeSSMClient) GetParameter(ctx context.Context, params *ssm.GetParameterInput, optFns ...func(*ssm.Options)) (*ssm.GetParameterOutput, error) {
	if f.err != nil {
		return nil, f.err
	}
	return &ssm.GetParameterOutput{Parameter: &ssmtypes.Parameter{Value: aws.String(f.value)}}, nil
}

type fakeLambdaClient struct {
	payload       string
	functionError string
	err           error
}

func (f *fakeLambdaClient) Invoke(ctx context.Context, params *lambda.InvokeInput, optFns ...func(*lambda.Options)) (*lambda.InvokeOutput, error) {
	if f.err != nil {
		return nil, f.err
	}
	out := &lambda.InvokeOutput{Payload: []byte(f.payload)}
	if f.functionError != "" {
		out.FunctionError = aws.String(f.functionError)
	}
	return out, nil
}

func resetCache() {
	cache = registryCache{}
}

func rpcCall(t *testing.T, body string) map[string]any {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/mcp", strings.NewReader(body))
	rec := httptest.NewRecorder()
	handleMCP(rec, req)

	var resp map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("invalid JSON response: %v (body=%s)", err, rec.Body.String())
	}
	return resp
}

func TestHandleHealth(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	handleHealth(rec, req)

	if got := rec.Body.String(); got != `{"status":"ok"}` {
		t.Fatalf("unexpected body: %s", got)
	}
}

func TestHandleMCP_Initialize(t *testing.T) {
	resp := rpcCall(t, `{"jsonrpc":"2.0","id":1,"method":"initialize"}`)

	result, ok := resp["result"].(map[string]any)
	if !ok {
		t.Fatalf("expected a result object, got %+v", resp)
	}
	if result["protocolVersion"] == "" {
		t.Fatalf("expected a protocolVersion, got %+v", result)
	}
}

func TestHandleMCP_UnknownMethod(t *testing.T) {
	resp := rpcCall(t, `{"jsonrpc":"2.0","id":1,"method":"nope"}`)

	errObj, ok := resp["error"].(map[string]any)
	if !ok {
		t.Fatalf("expected an error object, got %+v", resp)
	}
	if int(errObj["code"].(float64)) != rpcMethodNotFound {
		t.Fatalf("expected code %d, got %v", rpcMethodNotFound, errObj["code"])
	}
}

func TestHandleMCP_ToolsList(t *testing.T) {
	resetCache()
	ssmClient = &fakeSSMClient{value: testRegistryJSON}
	defer resetCache()

	resp := rpcCall(t, `{"jsonrpc":"2.0","id":1,"method":"tools/list"}`)

	result := resp["result"].(map[string]any)
	tools := result["tools"].([]any)
	if len(tools) != 1 {
		t.Fatalf("expected 1 tool, got %d", len(tools))
	}
	first := tools[0].(map[string]any)
	if first["name"] != "echo" {
		t.Fatalf("expected tool name 'echo', got %v", first["name"])
	}
}

func TestHandleMCP_ToolsCall_Success(t *testing.T) {
	resetCache()
	ssmClient = &fakeSSMClient{value: testRegistryJSON}
	lambdaClient = &fakeLambdaClient{payload: `{"echoed":"hi"}`}
	defer resetCache()

	resp := rpcCall(t, `{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"echo","arguments":{"message":"hi"}}}`)

	result := resp["result"].(map[string]any)
	if isErr, _ := result["isError"].(bool); isErr {
		t.Fatalf("expected success, got error result: %+v", result)
	}
	content := result["content"].([]any)[0].(map[string]any)
	if content["text"] != `{"echoed":"hi"}` {
		t.Fatalf("unexpected content text: %v", content["text"])
	}
}

func TestHandleMCP_ToolsCall_UnknownTool(t *testing.T) {
	resetCache()
	ssmClient = &fakeSSMClient{value: testRegistryJSON}
	defer resetCache()

	resp := rpcCall(t, `{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"bogus","arguments":{}}}`)

	errObj, ok := resp["error"].(map[string]any)
	if !ok {
		t.Fatalf("expected an error object, got %+v", resp)
	}
	if int(errObj["code"].(float64)) != rpcMethodNotFound {
		t.Fatalf("expected code %d, got %v", rpcMethodNotFound, errObj["code"])
	}
}

func TestHandleMCP_ToolsCall_LambdaFunctionError(t *testing.T) {
	resetCache()
	ssmClient = &fakeSSMClient{value: testRegistryJSON}
	lambdaClient = &fakeLambdaClient{payload: `{"errorMessage":"boom"}`, functionError: "Unhandled"}
	defer resetCache()

	resp := rpcCall(t, `{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"echo","arguments":{}}}`)

	result := resp["result"].(map[string]any)
	if isErr, _ := result["isError"].(bool); !isErr {
		t.Fatalf("expected isError:true, got %+v", result)
	}
}

func TestCallTool_InvokeError(t *testing.T) {
	client := &fakeLambdaClient{err: context.DeadlineExceeded}
	tool := Tool{Name: "echo", LambdaARN: "arn:aws:lambda:us-east-1:123:function:echo"}

	result := callTool(context.Background(), client, tool, nil)

	if !result.IsError {
		t.Fatalf("expected an error result, got %+v", result)
	}
}
