package main

import "testing"

func TestEstimateCostUSD_KnownModel(t *testing.T) {
	cost := estimateCostUSD("us.anthropic.claude-haiku-4-5-20251001-v1:0", 1_000_000, 1_000_000)
	if cost != 6.00 {
		t.Fatalf("expected 6.00 (1.00 input + 5.00 output per 1M), got %v", cost)
	}
}

func TestEstimateCostUSD_UnknownModel(t *testing.T) {
	cost := estimateCostUSD("some-future-model", 1_000_000, 1_000_000)
	if cost != 0 {
		t.Fatalf("expected 0 for an unknown model, got %v", cost)
	}
}

func TestEstimateCostUSD_ZeroTokens(t *testing.T) {
	cost := estimateCostUSD("us.anthropic.claude-haiku-4-5-20251001-v1:0", 0, 0)
	if cost != 0 {
		t.Fatalf("expected 0 for zero tokens, got %v", cost)
	}
}
