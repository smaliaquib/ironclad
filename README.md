# Ironclad — frontend

The frontend for [Ironclad](https://github.com/smaliaquib/ironclad) — see the `master` branch for the full project overview and how this fits with the `router` and `agent` branches.

React + TypeScript (Vite) chat UI that streams responses from the router via SSE.

## Run

```
copy .env.example .env   # optional, defaults to http://localhost:8080
npm install
npm run dev
```

## Config (env vars)

- `VITE_ROUTER_URL` — base URL of the router service (default `http://localhost:8080`)

## Build

```
npm run build
```
