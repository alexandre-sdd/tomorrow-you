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
  return (
    <section className="chat-panel" aria-live="polite">
      {messages.length === 0 ? <p className="empty-text">{emptyText}</p> : null}
      {messages.map((message) => (
        <MessageBubble key={message.id} role={message.role} text={message.content} />
      ))}
    </section>
  );
}
