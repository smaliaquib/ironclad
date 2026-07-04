package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"time"
)

type invokeRequest struct {
	Message string `json:"message"`
}

var agentBaseURL string

func main() {
	agentBaseURL = os.Getenv("AGENT_URL")
	if agentBaseURL == "" {
		agentBaseURL = "http://localhost:8000"
	}

	addr := os.Getenv("ROUTER_ADDR")
	if addr == "" {
		addr = ":8080"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/invoke", withCORS(handleInvoke))
	mux.HandleFunc("/health", withCORS(handleHealth))

	log.Printf("router listening on %s, forwarding to agent at %s", addr, agentBaseURL)
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

func handleInvoke(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
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
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.WriteHeader(http.StatusOK)

	flusher, ok := w.(http.Flusher)
	reader := bufio.NewReader(resp.Body)
	for {
		line, err := reader.ReadBytes('\n')
		if len(line) > 0 {
			w.Write(line)
			if ok {
				flusher.Flush()
			}
		}
		if err != nil {
			if err != io.EOF {
				log.Printf("stream read error: %v", err)
			}
			break
		}
	}
}
