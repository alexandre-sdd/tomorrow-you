"use client";

import { useMemo, useState } from "react";
import ChatPanel from "../components/ChatPanel";
import InputBar from "../components/InputBar";
import ScreenHeader from "../components/ScreenHeader";
import SelfCardPanel from "../components/SelfCardPanel";
import { Message, SelfCard } from "../lib/types";

interface FutureSelfConversationScreenProps {
  selfCard: SelfCard;
}

const mockReplies = [
  "You are not choosing between comfort and ambition. You are choosing what kind of pressure you want to carry every day.",
  "If you move, design explicit rituals with your wife before anything else. Career momentum without relational rhythm will feel hollow.",
  "Run a reversible test first. Clarity often comes from a short lived experiment, not from one giant leap.",
  "Regret is usually less about the path and more about whether you chose consciously.",
];

function makeMessage(role: Message["role"], content: string): Message {
  return {
    id: `msg_${Date.now()}_${Math.random().toString(16).slice(2, 7)}`,
    role,
    content,
    timestamp: Date.now(),
  };
}

export default function FutureSelfConversationScreen({ selfCard }: FutureSelfConversationScreenProps) {
  const [messages, setMessages] = useState<Message[]>([
    makeMessage(
      "future_self",
      "I am the version of you that took this path. Ask directly, and I will answer directly.",
    ),
  ]);
  const [replyIndex, setReplyIndex] = useState(0);

  const responseCount = useMemo(
    () => messages.filter((msg) => msg.role === "future_self").length,
    [messages],
  );

  function handleUserSend(text: string) {
    setMessages((prev) => [...prev, makeMessage("user", text)]);
    const nextReply = mockReplies[replyIndex % mockReplies.length];
    setReplyIndex((prev) => prev + 1);

    window.setTimeout(() => {
      setMessages((prev) => [...prev, makeMessage("future_self", nextReply)]);
    }, 280);
  }

  return (
    <div className="screen screen--conversation">
      <ScreenHeader
        eyebrow="Future Conversation"
        title="Conversation with your selected self"
        subtitle="Text mode for now. Voice integration will sit behind the placeholder button."
      />

      <div className="conversation-layout">
        <SelfCardPanel selfCard={selfCard} />

        <section className="conversation-stack">
          <div className="conversation-toolbar">
            <p>{responseCount} future-self response{responseCount === 1 ? "" : "s"}</p>
            <button className="button-secondary" type="button">
              Voice (soon)
            </button>
          </div>
          <ChatPanel messages={messages} className="chat-panel--conversation" />
          <InputBar
            placeholder="Ask your future self..."
            submitLabel="↑"
            onSubmit={handleUserSend}
          />
        </section>
      </div>
    </div>
  );
}
