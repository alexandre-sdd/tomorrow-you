"use client";

import { useEffect, useMemo, useState } from "react";
import clsx from "./clsx";

interface MessageBubbleProps {
  role: "user" | "assistant" | "system";
  text: string;
  animate?: boolean;
  onAnimationComplete?: () => void;
}

function charsPerTick(textLength: number): number {
  if (textLength > 800) {
    return 10;
  }
  if (textLength > 400) {
    return 6;
  }
  if (textLength > 180) {
    return 4;
  }
  return 2;
}

export function MessageBubble({
  role,
  text,
  animate = false,
  onAnimationComplete,
}: MessageBubbleProps) {
  const [displayText, setDisplayText] = useState(text);
  const [isAnimating, setIsAnimating] = useState(false);

  const shouldAnimate = useMemo(() => {
    return animate && role === "assistant" && text.length > 0;
  }, [animate, role, text.length]);

  useEffect(() => {
    if (!shouldAnimate) {
      setDisplayText(text);
      setIsAnimating(false);
      onAnimationComplete?.();
      return;
    }

    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduceMotion) {
      setDisplayText(text);
      setIsAnimating(false);
      onAnimationComplete?.();
      return;
    }

    let index = 0;
    const step = charsPerTick(text.length);

    setDisplayText("");
    setIsAnimating(true);

    const intervalId = window.setInterval(() => {
      index = Math.min(text.length, index + step);
      setDisplayText(text.slice(0, index));

      if (index >= text.length) {
        window.clearInterval(intervalId);
        setIsAnimating(false);
        onAnimationComplete?.();
      }
    }, 18);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [onAnimationComplete, shouldAnimate, text]);

  return (
    <article
      className={clsx(
        "message-bubble",
        role === "user" ? "message-user" : role === "system" ? "message-system" : "message-assistant",
      )}
    >
      <p>
        {displayText}
        {isAnimating ? <span className="typing-cursor" aria-hidden="true">|</span> : null}
      </p>
    </article>
  );
}
