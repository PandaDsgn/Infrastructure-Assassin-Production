import React, { useState, useEffect, useRef } from "react";

export default function ChatWidget({ collapsed, toggleChat }) {
  const [messages, setMessages] = useState([
    {
      role: "ai",
      text: "Hello. I am the Infrastructure Assassin AI. How can I assist you with today's audit?",
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const chatEndRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Load initial history
  useEffect(() => {
    const fetchHistory = async () => {
      const token = sessionStorage.getItem("aegis_token");
      if (!token) return;
      try {
        const res = await fetch("/api/chat/history", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const history = await res.json();
          if (history.length > 0) {
            const formatted = history.map((msg) => ({
              role: msg.startsWith("User:") ? "user" : "ai",
              text: msg.replace(/^(User:|Assassin AI:|System:)/, "").trim(),
            }));
            setMessages(formatted);
          }
        }
      } catch (err) {
        console.error("Failed to load chat history", err);
      }
    };
    fetchHistory();
  }, []);

  const sendMessage = async () => {
    if (!inputValue.trim()) return;
    const userMsg = inputValue.trim();
    setInputValue("");

    setMessages((prev) => [...prev, { role: "user", text: userMsg }]);
    setIsTyping(true);

    try {
      const token = sessionStorage.getItem("aegis_token");
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: userMsg }),
      });
      const data = await response.json();

      const aiResponseText = data.error ? (
        <span style={{ color: "var(--danger)" }}>{data.error}</span>
      ) : (
        <span>
          {data.reply}
          {data.source && (
            <div
              style={{
                fontSize: "0.7rem",
                color: "var(--success)",
                marginTop: "4px",
                fontWeight: 500,
              }}
            >
              ● {data.source}
            </div>
          )}
        </span>
      );

      setMessages((prev) => [...prev, { role: "ai", text: aiResponseText }]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: "Error communicating with AI core." },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div id="chat-widget" className={collapsed ? "collapsed" : ""}>
      <div id="chat-header">
        <span>Agent Chat Interface</span>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span
            style={{
              height: "8px",
              width: "8px",
              background: "var(--success)",
              borderRadius: "50%",
              display: "inline-block",
            }}
          ></span>
          <button
            className="chat-toggle-btn"
            title="Close chat"
            onClick={toggleChat}
          >
            &times;
          </button>
        </div>
      </div>

      <div id="chat-history">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`msg ${msg.role === "user" ? "msg-user" : "msg-ai"}`}
          >
            {msg.text}
          </div>
        ))}
        {isTyping && (
          <div className="msg msg-ai">
            <em>Analyzing database...</em>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <div className="chat-help-bar">
        💡 Type <strong>/use groq</strong>, <strong>/use deepseek</strong>, or{" "}
        <strong>/use auto</strong> to manually switch AI tiers.
      </div>

      <div id="chat-input-area">
        <input
          type="text"
          id="chat-input"
          placeholder="Ask about the infrastructure..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={(e) => e.key === "Enter" && sendMessage()}
        />
        <button id="chat-send" onClick={sendMessage}>
          Send
        </button>
      </div>
    </div>
  );
}
