import type { Tokens } from "./cognito";

// Same-origin relative paths, same pattern api/invoke.ts uses - hits
// CloudFront's edge-auth Lambda directly, never the ALB. Cookies flow
// automatically since these are same-origin requests.

export async function establishSession(tokens: Tokens): Promise<void> {
  const res = await fetch("/auth/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id_token: tokens.idToken,
      access_token: tokens.accessToken,
      refresh_token: tokens.refreshToken,
    }),
  });
  if (!res.ok) {
    throw new Error(`failed to establish session: ${res.status}`);
  }
}

export async function whoami(): Promise<boolean> {
  try {
    const res = await fetch("/auth/whoami");
    if (!res.ok) return false;
    const body = (await res.json()) as { authenticated: boolean };
    return body.authenticated;
  } catch {
    return false;
  }
}

export async function logout(): Promise<void> {
  await fetch("/auth/logout", { method: "POST" });
}
