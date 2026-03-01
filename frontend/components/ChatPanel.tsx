import { Message } from "../lib/types";
import MessageBubble from "./MessageBubble";

interface ChatPanelProps {
  messages: Message[];
  className?: string;
}

export default function ChatPanel({ messages, className }: ChatPanelProps) {
  return (
    <section className={`chat-panel ${className ?? ""}`}>
      {messages.map((message) => (
        <MessageBubble key={message.id} role={message.role} content={message.content} />
      ))}
    </section>
  );
}
