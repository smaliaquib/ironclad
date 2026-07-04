// Mirrors the infra's enable_auth flag (baked in at build time). While off,
// CloudFront's Lambda@Edge isn't attached and the router has no REQUIRE_AUTH,
// so nothing auth-related (login gate, /auth/whoami, /usage) should be
// exercised at all.
export const AUTH_ENABLED = import.meta.env.VITE_ENABLE_AUTH === "true";
