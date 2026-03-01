"use client";

import { FormEvent, useState } from "react";
import { ScreenHeader } from "@/components/ScreenHeader";

interface LandingScreenProps {
  isLoading: boolean;
  onBegin: (params: { sessionId: string; userName: string }) => Promise<void>;
}

function defaultSessionId(): string {
  return `web_${Date.now()}`;
}

export function LandingScreen({ isLoading, onBegin }: LandingScreenProps) {
  const [sessionId, setSessionId] = useState(defaultSessionId());
  const [userName, setUserName] = useState("User");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onBegin({ sessionId: sessionId.trim(), userName: userName.trim() || "User" });
  };

  return (
    <section className="hero-card">
      <div className="hero-icon" aria-hidden="true">
        ✧
      </div>
      <ScreenHeader
        title="Meet the future versions of you"
        subtitle="An AI gets to know your values and crossroads, then helps you explore your multiverse one path at a time."
      />
      <form className="hero-form" onSubmit={submit}>
        <label>
          <span>Session ID</span>
          <input
            value={sessionId}
            onChange={(event) => setSessionId(event.target.value)}
            disabled={isLoading}
            required
          />
        </label>
        <label>
          <span>Name</span>
          <input
            value={userName}
            onChange={(event) => setUserName(event.target.value)}
            disabled={isLoading}
            required
          />
        </label>
        <button type="submit" disabled={isLoading || !sessionId.trim()}>
          {isLoading ? "Starting..." : "Begin your journey"}
        </button>
      </form>
    </section>
  );
}
