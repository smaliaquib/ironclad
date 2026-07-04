package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHandleHealth(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	withCORS(handleHealth)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
	if got := rec.Body.String(); got != `{"status":"ok"}` {
		t.Fatalf("unexpected body: %s", got)
	}
}

func TestWithCORS_OptionsRequest(t *testing.T) {
	req := httptest.NewRequest(http.MethodOptions, "/invoke", nil)
	rec := httptest.NewRecorder()

	withCORS(handleInvoke)(rec, req)

	if rec.Code != http.StatusNoContent {
		t.Fatalf("expected status 204, got %d", rec.Code)
	}
	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "*" {
		t.Fatalf("expected CORS header, got %q", got)
	}
}

func TestHandleInvoke_MethodNotAllowed(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/invoke", nil)
	rec := httptest.NewRecorder()

	handleInvoke(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("expected status 405, got %d", rec.Code)
	}
}

func TestHandleInvoke_MissingMessage(t *testing.T) {
	req := httptest.NewRequest(http.MethodPost, "/invoke", strings.NewReader(`{"message":""}`))
	rec := httptest.NewRecorder()

	handleInvoke(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", rec.Code)
	}
}

func TestHandleInvoke_ProxiesToAgent(t *testing.T) {
	agent := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/invoke" {
			t.Errorf("expected agent path /invoke, got %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte("event: done\ndata: {}\n\n"))
	}))
	defer agent.Close()

	original := agentBaseURL
	agentBaseURL = agent.URL
	defer func() { agentBaseURL = original }()

	req := httptest.NewRequest(http.MethodPost, "/invoke", strings.NewReader(`{"message":"hi"}`))
	rec := httptest.NewRecorder()

	handleInvoke(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
	if got := rec.Body.String(); got != "event: done\ndata: {}\n\n" {
		t.Fatalf("expected proxied SSE body, got %q", got)
	}
}
