import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { invokeAgent } from "./api/invoke";
import "./App.css";

interface Message {
  role: "user" | "assistant";
  content: string;
  error?: boolean;
}

const SUGGESTIONS = [
  "What can you help me with?",
  "Summarize how this app works",
  "Give me three ideas for a side project",
];

interface AppProps {
  onSignOut?: () => void;
  onUnauthorized: () => void;
}

function App({ onSignOut, onUnauthorized }: AppProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", content: trimmed },
      { role: "assistant", content: "" },
    ]);
    setInput("");
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    await invokeAgent(
      trimmed,
      {
        onToken: (token) => {
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: next[next.length - 1].content + token,
            };
            return next;
          });
        },
        onDone: () => setIsStreaming(false),
        onError: (message) => {
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { role: "assistant", content: message, error: true };
            return next;
          });
          setIsStreaming(false);
        },
        onUnauthorized: () => {
          setIsStreaming(false);
          onUnauthorized();
        },
      },
      controller.signal,
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          Ironclad
        </div>
        {onSignOut && (
          <button className="sign-out-btn" onClick={onSignOut}>
            Sign out
          </button>
        )}
      </header>

      {isEmpty ? (
        <div className="empty-state">
          <span className="empty-mark" aria-hidden="true" />
          <h1>What can I help with?</h1>
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="suggestion-chip" onClick={() => sendMessage(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="messages">
          {messages.map((m, i) => {
            const isLast = i === messages.length - 1;
            const isThinking = m.role === "assistant" && !m.content && isStreaming && isLast;
            return (
              <div key={i} className={`message message-${m.role}`}>
                {m.role === "assistant" && <div className="avatar" aria-hidden="true" />}
                <div className="bubble-col">
                  <div className={`bubble ${m.error ? "bubble-error" : ""}`}>
                    {isThinking ? (
                      <span className="thinking">
                        <span />
                        <span />
                        <span />
                      </span>
                    ) : m.role === "assistant" && !m.error ? (
                      <>
                        <div className="markdown">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                        </div>
                        {isStreaming && isLast && <span className="cursor" />}
                      </>
                    ) : (
                      m.content
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          <div ref={scrollRef} />
        </div>
      )}

      <div className="composer-wrap">
        <div className="composer">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask something..."
            rows={1}
            disabled={isStreaming}
          />
          <button
            className="send-btn"
            onClick={() => sendMessage(input)}
            disabled={isStreaming || !input.trim()}
            aria-label="Send message"
          >
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 19V5" />
              <path d="M5 12l7-7 7 7" />
            </svg>
          </button>
        </div>
        <div className="composer-hint">Enter to send · Shift+Enter for a new line</div>
      </div>
    </div>
  );
}

export default App;
