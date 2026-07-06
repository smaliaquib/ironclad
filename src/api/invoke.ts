// Empty (the default) means "same origin, relative path" - correct whenever
// the frontend is served from behind the same gateway (ALB or CloudFront)
// that path-routes /invoke* to ai-gateway. Only needed as an absolute URL
// for local dev / docker-compose, where frontend and ai-gateway run on
// different origins - see .env.example.
const AI_GATEWAY_URL = import.meta.env.VITE_AI_GATEWAY_URL ?? "";

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface InvokeCallbacks {
  onToken: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
  /** Session expired or was never established - caller should show the login page. */
  onUnauthorized: () => void;
  /** ai-gateway appends this after "done" with the caller's updated daily total. */
  onUsageUpdate?: (used: number, limit: number) => void;
  /** The agent sends this before any tokens, if the knowledge base returned matches. */
  onSources?: (sources: string[]) => void;
}

interface SSEEvent {
  event: string;
  data: string;
}

function parseSSEBlock(block: string): SSEEvent | null {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}

export async function invokeAgent(
  message: string,
  history: HistoryMessage[],
  callbacks: InvokeCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const { onToken, onDone, onError, onUnauthorized, onUsageUpdate, onSources } = callbacks;

  let response: Response;
  try {
    response = await fetch(`${AI_GATEWAY_URL}/invoke`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
      signal,
    });
  } catch (err) {
    onError(err instanceof Error ? err.message : "network error");
    return;
  }

  if (response.status === 401) {
    onUnauthorized();
    return;
  }
  if (response.status === 429) {
    onError("You've reached today's usage limit - try again tomorrow.");
    return;
  }
  if (!response.ok || !response.body) {
    onError(`request failed: ${response.status}`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawDone = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    let separatorIndex: number;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);

      const parsed = parseSSEBlock(block);
      if (!parsed) continue;

      if (parsed.event === "token") {
        const { text } = JSON.parse(parsed.data) as { text: string };
        onToken(text);
      } else if (parsed.event === "sources") {
        const { sources } = JSON.parse(parsed.data) as { sources: string[] };
        onSources?.(sources);
      } else if (parsed.event === "usage_total") {
        const usage = JSON.parse(parsed.data) as { used: number; limit: number };
        onUsageUpdate?.(usage.used, usage.limit);
      } else if (parsed.event === "done") {
        // Keep reading rather than returning here - ai-gateway appends a
        // usage_total event after "done" in the same stream, so bailing out
        // now would mean never seeing it.
        sawDone = true;
        onDone();
      } else if (parsed.event === "error") {
        const { message: errMessage } = JSON.parse(parsed.data) as { message: string };
        onError(errMessage);
        return;
      }
    }
  }

  if (!sawDone) onDone();
}
