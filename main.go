package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
)

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type invokeRequest struct {
	Message string        `json:"message"`
	History []chatMessage `json:"history,omitempty"`
}

var agentBaseURL string

func main() {
	agentBaseURL = os.Getenv("AGENT_URL")
	if agentBaseURL == "" {
		agentBaseURL = "http://localhost:8000"
	}

	addr := os.Getenv("AI_GATEWAY_ADDR")
	if addr == "" {
		addr = ":8080"
	}

	requireAuth, _ = strconv.ParseBool(os.Getenv("REQUIRE_AUTH"))
	if requireAuth {
		region := os.Getenv("AWS_REGION")
		userPoolID := os.Getenv("COGNITO_USER_POOL_ID")
		clientID := os.Getenv("COGNITO_CLIENT_ID")
		if err := initAuth(userPoolID, clientID, region); err != nil {
			log.Fatalf("auth init failed: %v", err)
		}

		usageTable = os.Getenv("USAGE_TABLE_NAME")
		dailyTokenLimit, _ = strconv.Atoi(os.Getenv("DAILY_TOKEN_LIMIT"))
		if dailyTokenLimit == 0 {
			dailyTokenLimit = 10000
		}
		cfg, err := config.LoadDefaultConfig(context.Background(), config.WithRegion(region))
		if err != nil {
			log.Fatalf("aws config load failed: %v", err)
		}
		dynamoClient = dynamodb.NewFromConfig(cfg)

		log.Printf("auth enabled: user pool %s, daily token limit %d", userPoolID, dailyTokenLimit)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/invoke", withCORS(handleInvoke))
	mux.HandleFunc("/invoke/usage", withCORS(handleUsage))
	mux.HandleFunc("/health", withCORS(handleHealth))

	log.Printf("ai-gateway listening on %s, forwarding to agent at %s", addr, agentBaseURL)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}

func withCORS(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next(w, r)
	}
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Write([]byte(`{"status":"ok"}`))
}

type usageStatus struct {
	Used  int `json:"used"`
	Limit int `json:"limit"`
}

// handleUsage reports the caller's token usage for today, so the frontend
// can show it before the first message of a session is even sent.
func handleUsage(w http.ResponseWriter, r *http.Request) {
	if !requireAuth {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}

	userID, err := verifyIDToken(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	used, err := getUsedToday(r.Context(), userID)
	if err != nil {
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(usageStatus{Used: used, Limit: dailyTokenLimit})
}

func handleInvoke(w http.ResponseWriter, r *http.Request) {
	start := time.Now()

	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var userID string
	var usedToday int
	if requireAuth {
		var err error
		userID, err = verifyIDToken(r)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		used, err := getUsedToday(r.Context(), userID)
		if err != nil {
			log.Printf("usage check failed: %v", err)
		} else {
			usedToday = used
			if used >= dailyTokenLimit {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusTooManyRequests)
				json.NewEncoder(w).Encode(map[string]any{
					"error": "daily token limit exceeded",
					"used":  used,
					"limit": dailyTokenLimit,
				})
				emitUsageMetric(userID, "", "rate_limited", 0, 0, 0,
					float64(time.Since(start).Milliseconds()), used, dailyTokenLimit)
				return
			}
		}
	}

	var req invokeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request body", http.StatusBadRequest)
		return
	}
	if req.Message == "" {
		http.Error(w, "message is required", http.StatusBadRequest)
		return
	}

	body, err := json.Marshal(req)
	if err != nil {
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}

	agentReq, err := http.NewRequestWithContext(r.Context(), http.MethodPost, agentBaseURL+"/invoke", bytes.NewReader(body))
	if err != nil {
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	agentReq.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 5 * time.Minute}
	resp, err := client.Do(agentReq)
	if err != nil {
		http.Error(w, "agent unavailable", http.StatusBadGateway)
		if requireAuth {
			emitUsageMetric(userID, "", "error", 0, 0, 0,
				float64(time.Since(start).Milliseconds()), usedToday, dailyTokenLimit)
		}
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.WriteHeader(http.StatusOK)

	flusher, ok := w.(http.Flusher)
	reader := bufio.NewReader(resp.Body)
	var sseEvent string
	var usage usageEvent
	for {
		line, err := reader.ReadBytes('\n')
		if len(line) > 0 {
			w.Write(line)
			if ok {
				flusher.Flush()
			}
			sseEvent, usage = trackUsageEvent(line, sseEvent, usage)
		}
		if err != nil {
			if err != io.EOF {
				log.Printf("stream read error: %v", err)
			}
			break
		}
	}

	if requireAuth {
		latencyMs := float64(time.Since(start).Milliseconds())
		tokens := usage.InputTokens + usage.OutputTokens

		if tokens > 0 {
			status := "success"
			dailyUsed := tokens
			newTotal, err := recordUsage(context.Background(), userID, tokens)
			if err != nil {
				log.Printf("recording usage failed: %v", err)
			} else {
				dailyUsed = newTotal
				fmt.Fprintf(w, "event: usage_total\ndata: {\"used\":%d,\"limit\":%d}\n\n", newTotal, dailyTokenLimit)
				if ok {
					flusher.Flush()
				}
			}
			emitUsageMetric(userID, usage.ModelID, status, usage.InputTokens, usage.OutputTokens,
				usage.ToolCalls, latencyMs, dailyUsed, dailyTokenLimit)
		} else {
			// Stream ended with no usable token count - the agent hit its
			// own error path (event: error) rather than completing normally.
			emitUsageMetric(userID, usage.ModelID, "error", 0, 0, usage.ToolCalls,
				latencyMs, usedToday, dailyTokenLimit)
		}
	}
}

type usageEvent struct {
	InputTokens  int    `json:"input_tokens"`
	OutputTokens int    `json:"output_tokens"`
	ModelID      string `json:"model_id"`
	ToolCalls    int    `json:"tool_calls"`
}

// trackUsageEvent watches the SSE stream being proxied through for an
// "event: usage" block and parses its "data:" line - the agent emits this
// right before "done" so ai-gateway can record actual Bedrock token usage
// without the agent needing to know about users or limits. sseEvent/usage
// are threaded through by the caller since this is called once per line.
func trackUsageEvent(line []byte, sseEvent string, usage usageEvent) (string, usageEvent) {
	text := strings.TrimRight(string(line), "\r\n")
	switch {
	case strings.HasPrefix(text, "event:"):
		return strings.TrimSpace(strings.TrimPrefix(text, "event:")), usage
	case strings.HasPrefix(text, "data:") && sseEvent == "usage":
		var parsed usageEvent
		if err := json.Unmarshal([]byte(strings.TrimSpace(strings.TrimPrefix(text, "data:"))), &parsed); err == nil {
			usage = parsed
		}
		return sseEvent, usage
	case text == "":
		return "", usage
	default:
		return sseEvent, usage
	}
}
