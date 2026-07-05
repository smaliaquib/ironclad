package main

import (
	_ "embed"
	"net/http"
)

//go:embed openapi.yaml
var openapiSpec []byte

// handleOpenAPI serves a fixed, hand-written OpenAPI 3.0 document describing
// this gateway's own /mcp and /health endpoints. There's no per-tool
// business logic here to generate docs from - the gateway is a thin
// dispatcher, so a static file is the accurate description of its surface.
func handleOpenAPI(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/yaml")
	w.Write(openapiSpec)
}
