"use client";

import { useEffect, useMemo, useState } from "react";
import ChatPanel from "../components/ChatPanel";
import InputBar from "../components/InputBar";
import ScreenHeader from "../components/ScreenHeader";
import { completeInterview, replyInterview, startInterview } from "../lib/api";
import { Message, SelfCard, UserProfile } from "../lib/types";

interface InterviewScreenProps {
  onComplete: (payload: {
    sessionId: string;
    profile: UserProfile | null;
    currentSelf: SelfCard | null;
  }) => void;
}

function makeMessage(role: Message["role"], content: string): Message {
  return {
    id: `msg_${Date.now()}_${Math.random().toString(16).slice(2, 7)}`,
    role,
    content,
    timestamp: Date.now(),
  };
}

export default function InterviewScreen({ onComplete }: InterviewScreenProps) {
  const [sessionId] = useState(
    () => `fe_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [isReady, setIsReady] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profileCompleteness, setProfileCompleteness] = useState(0);
  const [answerCount, setAnswerCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function initializeInterview() {
      try {
        const result = await startInterview(sessionId, "User");
        if (cancelled) {
          return;
        }
        setMessages([makeMessage("interviewer", result.agentMessage)]);
        setProfileCompleteness(result.profileCompleteness);
        setIsReady(true);
      } catch (exc) {
        if (cancelled) {
          return;
        }
        const message = exc instanceof Error ? exc.message : "Could not start interview.";
        setError(`Interview API unavailable: ${message}`);
        setMessages([
          makeMessage(
            "interviewer",
            "Interview service is unavailable. Check backend and try again.",
          ),
        ]);
      }
    }

    void initializeInterview();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const canFinalize = profileCompleteness >= 0.5 || answerCount >= 4;
  const progressLabel = useMemo(() => {
    const pct = Math.round(profileCompleteness * 100);
    return `${pct}%`;
  }, [profileCompleteness]);

  async function handleAnswer(text: string) {
    if (!isReady || isSending || isFinalizing) {
      return;
    }
    setError(null);
    setIsSending(true);
    setMessages((prev) => [...prev, makeMessage("user", text)]);
    setAnswerCount((prev) => prev + 1);

    try {
      const result = await replyInterview(sessionId, text);
      setProfileCompleteness(result.profileCompleteness);
      setMessages((prev) => [...prev, makeMessage("interviewer", result.agentMessage)]);
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : "Interview request failed.";
      setError(message);
      setMessages((prev) => [
        ...prev,
        makeMessage(
          "interviewer",
          "I could not process that through the interview service. Please try again.",
        ),
      ]);
    } finally {
      setIsSending(false);
    }
  }

  async function handleFinalize() {
    if (isFinalizing) {
      return;
    }
    setIsFinalizing(true);
    setError(null);
    try {
      const result = await completeInterview(sessionId);
      onComplete({
        sessionId: result.sessionId,
        profile: result.userProfile,
        currentSelf: result.currentSelf,
      });
    } catch (exc) {
      const message =
        exc instanceof Error ? exc.message : "Could not complete interview.";
      setError(message);
      onComplete({
        sessionId,
        profile: null,
        currentSelf: null,
      });
    } finally {
      setIsFinalizing(false);
    }
  }

  return (
    <div className="screen screen--interview">
      <ScreenHeader
        eyebrow="Interview"
        title="Your Multiverse Interview"
        subtitle="Profile completeness"
      />

      <div className="interview-body">
        <p className="screen-progress">{progressLabel}</p>
        {error && <p className="screen-error">{error}</p>}
        <ChatPanel messages={messages} className="chat-panel--interview" />
      </div>

      <div className="interview-footer">
        <InputBar
          placeholder={isReady ? "Type your response..." : "Starting interview..."}
          submitLabel={isSending ? "..." : "↑"}
          onSubmit={handleAnswer}
          disabled={!isReady || isSending || isFinalizing}
        />
        <button
          className="button-inline"
          type="button"
          onClick={handleFinalize}
          disabled={!canFinalize || isFinalizing}
        >
          {isFinalizing ? "Finalizing..." : "Complete"}
        </button>
      </div>
    </div>
  );
}
