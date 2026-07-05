package main

import (
	"encoding/json"
	"fmt"
	"log"
	"time"
)

// emitUsageMetric writes one CloudWatch Embedded Metric Format (EMF) JSON
// line to stdout per completed /invoke request. CloudWatch Logs auto-detects
// the "_aws" block and turns it into real custom metrics (namespace
// Ironclad/Usage, dimensioned by Model+Status only - bounded, cheap) while
// the same line stays fully queryable via Logs Insights, where the flat
// fields below (user_id in particular) support per-user breakdowns without
// the cardinality cost of making user_id a metric dimension.
func emitUsageMetric(userID, modelID, status string, inputTokens, outputTokens, toolCalls int, latencyMs float64, dailyUsed, dailyLimit int) {
	totalTokens := inputTokens + outputTokens
	cost := estimateCostUSD(modelID, inputTokens, outputTokens)

	record := map[string]any{
		"_aws": map[string]any{
			"Timestamp": time.Now().UnixMilli(),
			"CloudWatchMetrics": []map[string]any{
				{
					"Namespace":  "Ironclad/Usage",
					"Dimensions": [][]string{{"Model", "Status"}},
					"Metrics": []map[string]string{
						{"Name": "RequestCount"},
						{"Name": "InputTokens"},
						{"Name": "OutputTokens"},
						{"Name": "TotalTokens"},
						{"Name": "CostUsd"},
						{"Name": "LatencyMs"},
						{"Name": "ToolCalls"},
					},
				},
			},
		},
		"Model":        modelID,
		"Status":       status,
		"RequestCount": 1,
		"InputTokens":  inputTokens,
		"OutputTokens": outputTokens,
		"TotalTokens":  totalTokens,
		"CostUsd":      cost,
		"LatencyMs":    latencyMs,
		"ToolCalls":    toolCalls,
		// Flat fields below aren't part of the metric - they ride along on
		// the same log line purely for Logs Insights per-user queries.
		"user_id":         userID,
		"daily_used":      dailyUsed,
		"daily_limit":     dailyLimit,
		"daily_remaining": dailyLimit - dailyUsed,
	}

	b, err := json.Marshal(record)
	if err != nil {
		log.Printf("failed to marshal usage metric: %v", err)
		return
	}
	// fmt.Println, not log.Println - the default logger prepends a
	// timestamp prefix, which would break CloudWatch's EMF auto-detection
	// (the line must *be* valid JSON, nothing before the opening brace).
	fmt.Println(string(b))
}
