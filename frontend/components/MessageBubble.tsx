import { MessageRole } from "../lib/types";

interface MessageBubbleProps {
  role: MessageRole;
  content: string;
}

export default function MessageBubble({ role, content }: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div className={`message-row ${isUser ? "message-row--user" : "message-row--agent"}`}>
      <div className={`message-bubble ${isUser ? "message-bubble--user" : "message-bubble--agent"}`}>
        <p className="message-bubble__text">{content}</p>
      </div>
    </div>
  );
}
