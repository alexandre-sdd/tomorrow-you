"use client";

import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
}

interface ChatPanelProps {
  messages: ChatMessage[];
  emptyText: string;
}

export function ChatPanel({ messages, emptyText }: ChatPanelProps) {
  const animatedIdsRef = useRef<Set<string>>(new Set());
  const panelRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) {
      return;
    }
    panel.scrollTop = panel.scrollHeight;
  }, [messages]);

  return (
    <section ref={panelRef} className="chat-panel" aria-live="polite">
      {messages.length === 0 ? <p className="empty-text">{emptyText}</p> : null}
      {messages.map((message, index) => {
        const isLatestAssistant =
          message.role === "assistant" && index === messages.length - 1;
        const shouldAnimate =
          isLatestAssistant && !animatedIdsRef.current.has(message.id);

        return (
          <MessageBubble
            key={message.id}
            role={message.role}
            text={message.content}
            animate={shouldAnimate}
            onAnimationComplete={() => {
              animatedIdsRef.current.add(message.id);
            }}
          />
        );
      })}
    </section>
  );
}
