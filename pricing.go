package main

import "log"

// modelPricing is a manually-maintained table (Bedrock has no live pricing
// API) of $/1M tokens by Bedrock model ID. Verify against
// https://aws.amazon.com/bedrock/pricing/ for your region before trusting
// the cost numbers this produces - list prices can lag or vary by region.
var modelPricing = map[string]struct {
	InputPer1M  float64
	OutputPer1M float64
}{
	"us.anthropic.claude-haiku-4-5-20251001-v1:0": {InputPer1M: 1.00, OutputPer1M: 5.00},
}

// estimateCostUSD returns 0 (with a logged warning, not an error) for a
// model ID not in modelPricing - an unrecognized/new model shouldn't crash
// usage reporting, it should just report an obviously-incomplete cost until
// someone adds a pricing entry for it.
func estimateCostUSD(modelID string, inputTokens, outputTokens int) float64 {
	p, ok := modelPricing[modelID]
	if !ok {
		if modelID != "" {
			log.Printf("no pricing entry for model %q, reporting $0 cost", modelID)
		}
		return 0
	}
	return float64(inputTokens)/1_000_000*p.InputPer1M + float64(outputTokens)/1_000_000*p.OutputPer1M
}
