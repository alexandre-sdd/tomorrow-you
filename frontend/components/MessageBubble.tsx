import clsx from "./clsx";

interface MessageBubbleProps {
  role: "user" | "assistant" | "system";
  text: string;
}

export function MessageBubble({ role, text }: MessageBubbleProps) {
  return (
    <article
      className={clsx(
        "message-bubble",
        role === "user" ? "message-user" : role === "system" ? "message-system" : "message-assistant",
      )}
    >
      <p>{text}</p>
    </article>
  );
}
