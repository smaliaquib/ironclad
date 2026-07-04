import { afterEach, describe, expect, it, vi } from "vitest";
import { invokeAgent } from "./invoke";

function sseResponse(chunks: string[]): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
}

describe("invokeAgent", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("streams token events and calls onDone", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          sseResponse([
            'event: token\ndata: {"text":"Hel"}\n\n',
            'event: token\ndata: {"text":"lo"}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
        ),
    );

    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await invokeAgent("hi", { onToken, onDone, onError });

    expect(onToken).toHaveBeenNthCalledWith(1, "Hel");
    expect(onToken).toHaveBeenNthCalledWith(2, "lo");
    expect(onDone).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("calls onError on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 502 })));

    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await invokeAgent("hi", { onToken, onDone, onError });

    expect(onError).toHaveBeenCalledWith("request failed: 502");
    expect(onToken).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("calls onError on an error SSE event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(sseResponse(['event: error\ndata: {"message":"boom"}\n\n'])),
    );

    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await invokeAgent("hi", { onToken, onDone, onError });

    expect(onError).toHaveBeenCalledWith("boom");
    expect(onDone).not.toHaveBeenCalled();
  });
});
