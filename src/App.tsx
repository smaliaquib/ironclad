import { useRef, useState } from "react";
import { invokeAgent } from "./api/invoke";
import "./App.css";

interface Message {
  role: "user" | "assistant";
  content: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setInput("");
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    await invokeAgent(
      text,
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
            next[next.length - 1] = { role: "assistant", content: `Error: ${message}` };
            return next;
          });
          setIsStreaming(false);
        },
      },
      controller.signal
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="app">
      <header className="app-header">Ironclad</header>
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`message message-${m.role}`}>
            <div className="message-role">{m.role === "user" ? "You" : "Agent"}</div>
            <div className="message-content">{m.content || (isStreaming && i === messages.length - 1 ? "…" : "")}</div>
          </div>
        ))}
      </div>
      <div className="composer">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask something..."
          rows={2}
          disabled={isStreaming}
        />
        <button onClick={sendMessage} disabled={isStreaming || !input.trim()}>
          {isStreaming ? "Streaming…" : "Send"}
        </button>
      </div>
    </div>
  );
}

export default App;
