const ROUTER_URL = import.meta.env.VITE_ROUTER_URL ?? "http://localhost:8080";

export interface InvokeCallbacks {
  onToken: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
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

export async function invokeAgent(message: string, callbacks: InvokeCallbacks, signal?: AbortSignal): Promise<void> {
  const { onToken, onDone, onError } = callbacks;

  let response: Response;
  try {
    response = await fetch(`${ROUTER_URL}/invoke`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal,
    });
  } catch (err) {
    onError(err instanceof Error ? err.message : "network error");
    return;
  }

  if (!response.ok || !response.body) {
    onError(`request failed: ${response.status}`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

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
      } else if (parsed.event === "done") {
        onDone();
        return;
      } else if (parsed.event === "error") {
        const { message: errMessage } = JSON.parse(parsed.data) as { message: string };
        onError(errMessage);
        return;
      }
    }
  }

  onDone();
}
