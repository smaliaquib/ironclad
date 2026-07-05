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
    const onUnauthorized = vi.fn();

    await invokeAgent("hi", { onToken, onDone, onError, onUnauthorized });

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
    const onUnauthorized = vi.fn();

    await invokeAgent("hi", { onToken, onDone, onError, onUnauthorized });

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
    const onUnauthorized = vi.fn();

    await invokeAgent("hi", { onToken, onDone, onError, onUnauthorized });

    expect(onError).toHaveBeenCalledWith("boom");
    expect(onDone).not.toHaveBeenCalled();
  });

  it("calls onUnauthorized on a 401 response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();
    const onUnauthorized = vi.fn();

    await invokeAgent("hi", { onToken, onDone, onError, onUnauthorized });

    expect(onUnauthorized).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("calls onUsageUpdate for a usage_total event sent after done", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          sseResponse([
            'event: token\ndata: {"text":"hi"}\n\n',
            "event: done\ndata: {}\n\n",
            'event: usage_total\ndata: {"used":1234,"limit":10000}\n\n',
          ]),
        ),
    );

    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();
    const onUnauthorized = vi.fn();
    const onUsageUpdate = vi.fn();

    await invokeAgent("hi", { onToken, onDone, onError, onUnauthorized, onUsageUpdate });

    expect(onDone).toHaveBeenCalledOnce();
    expect(onUsageUpdate).toHaveBeenCalledWith(1234, 10000);
  });

  it("calls onSources for a sources event sent before tokens", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          sseResponse([
            'event: sources\ndata: {"sources":["a.pdf","b.txt"]}\n\n',
            'event: token\ndata: {"text":"hi"}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
        ),
    );

    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();
    const onUnauthorized = vi.fn();
    const onSources = vi.fn();

    await invokeAgent("hi", { onToken, onDone, onError, onUnauthorized, onSources });

    expect(onSources).toHaveBeenCalledWith(["a.pdf", "b.txt"]);
    expect(onToken).toHaveBeenCalledWith("hi");
  });

  it("calls onError with a friendly message on a 429 response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 429 })));

    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();
    const onUnauthorized = vi.fn();

    await invokeAgent("hi", { onToken, onDone, onError, onUnauthorized });

    expect(onError).toHaveBeenCalledWith(
      "You've reached today's usage limit - try again tomorrow.",
    );
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
