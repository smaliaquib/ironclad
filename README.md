# Ironclad — router

The router service for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview and how this fits with the `agent` and `frontend` branches.

Go service that exposes `POST /invoke`, forwards the request to the agent service, and streams the SSE response straight through to the caller.

## Run

```
go run .
```

## Config (env vars)

- `AGENT_URL` — base URL of the agent service (default `http://localhost:8000`)
- `ROUTER_ADDR` — listen address (default `:8080`)

## API

`POST /invoke` — body `{ "message": string }`, proxies to the agent and streams back `text/event-stream` unchanged.

`GET /health` — liveness check.
