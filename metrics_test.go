package main

import (
	"bufio"
	"encoding/json"
	"os"
	"testing"
)

// captureStdout redirects os.Stdout for the duration of fn and returns
// everything written to it. Used to verify emitUsageMetric's output line is
// itself valid JSON with nothing before the opening brace - fmt.Println
// (not log.Println, which would prepend a timestamp and break CloudWatch's
// EMF auto-detection) is what makes that true.
func captureStdout(t *testing.T, fn func()) string {
	t.Helper()
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatalf("failed to create pipe: %v", err)
	}
	original := os.Stdout
	os.Stdout = w
	defer func() { os.Stdout = original }()

	fn()

	w.Close()
	scanner := bufio.NewScanner(r)
	var out string
	if scanner.Scan() {
		out = scanner.Text()
	}
	return out
}

func TestEmitUsageMetric_ProducesValidEMFJSON(t *testing.T) {
	line := captureStdout(t, func() {
		emitUsageMetric("user-123", "us.anthropic.claude-haiku-4-5-20251001-v1:0", "success",
			100, 200, 1, 543.2, 300, 10000)
	})

	var parsed map[string]any
	if err := json.Unmarshal([]byte(line), &parsed); err != nil {
		t.Fatalf("emitUsageMetric output is not valid JSON: %v\nline: %q", err, line)
	}

	if _, ok := parsed["_aws"]; !ok {
		t.Fatalf("expected an _aws EMF metadata block, got: %v", parsed)
	}
	if parsed["Model"] != "us.anthropic.claude-haiku-4-5-20251001-v1:0" {
		t.Fatalf("expected Model field, got: %v", parsed["Model"])
	}
	if parsed["Status"] != "success" {
		t.Fatalf("expected Status=success, got: %v", parsed["Status"])
	}
	if parsed["user_id"] != "user-123" {
		t.Fatalf("expected user_id field, got: %v", parsed["user_id"])
	}
	if parsed["TotalTokens"].(float64) != 300 {
		t.Fatalf("expected TotalTokens=300, got: %v", parsed["TotalTokens"])
	}
	if parsed["daily_remaining"].(float64) != 9700 {
		t.Fatalf("expected daily_remaining=9700, got: %v", parsed["daily_remaining"])
	}
}
