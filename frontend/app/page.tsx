"use client";

import { useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import {
  branchConversation,
  completeInterview,
  getInterviewStatus,
  getPipelineStatus,
  replyConversation,
  replyInterview,
  startExploration,
  startInterview,
  type ConversationHistoryMessage,
  type PipelineStatusResponse,
} from "@/lib/api";
import type { SelfCard, UserProfile } from "@/lib/types";
import { ConversationScreen } from "@/screens/ConversationScreen";
import { InterviewScreen } from "@/screens/InterviewScreen";
import { LandingScreen } from "@/screens/LandingScreen";
import { ProfileRevealScreen } from "@/screens/ProfileRevealScreen";
import { SelfSelectionScreen } from "@/screens/SelfSelectionScreen";

type Step = "landing" | "interview" | "profile" | "selection" | "conversation";

interface UiMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
}

function createMessage(role: UiMessage["role"], content: string): UiMessage {
  return {
    id: `${role}_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    role,
    content,
  };
}

function mergeSelves(existing: SelfCard[], additions: SelfCard[]): SelfCard[] {
  const map = new Map(existing.map((selfCard) => [selfCard.id, selfCard]));
  for (const selfCard of additions) {
    map.set(selfCard.id, selfCard);
  }
  return Array.from(map.values()).sort((a, b) => a.depthLevel - b.depthLevel);
}

export default function HomePage() {
  const [step, setStep] = useState<Step>("landing");
  const [sessionId, setSessionId] = useState("");

  const [interviewMessages, setInterviewMessages] = useState<UiMessage[]>([]);
  const [profileCompleteness, setProfileCompleteness] = useState(0);
  const [isReadyForGeneration, setIsReadyForGeneration] = useState(false);

  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [currentSelf, setCurrentSelf] = useState<SelfCard | null>(null);
  const [futureSelves, setFutureSelves] = useState<SelfCard[]>([]);

  const [activeSelfId, setActiveSelfId] = useState<string | null>(null);
  const [historiesBySelf, setHistoriesBySelf] = useState<Record<string, ConversationHistoryMessage[]>>({});

  const [isStarting, setIsStarting] = useState(false);
  const [isSendingInterview, setIsSendingInterview] = useState(false);
  const [isRefreshingStatus, setIsRefreshingStatus] = useState(false);
  const [isCompletingOnboarding, setIsCompletingOnboarding] = useState(false);
  const [isSendingConversation, setIsSendingConversation] = useState(false);
  const [isBranching, setIsBranching] = useState(false);

  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const activeSelf = useMemo(() => {
    if (!activeSelfId) {
      return null;
    }
    return futureSelves.find((item) => item.id === activeSelfId) ?? null;
  }, [futureSelves, activeSelfId]);

  const withError = (fallback: string, err: unknown) => {
    const message = err instanceof Error ? err.message : fallback;
    setError(message || fallback);
  };

  const handleStart = async (params: { sessionId: string; userName: string }) => {
    setError("");
    setInfo("");
    setIsStarting(true);

    try {
      const started = await startInterview(params.sessionId, params.userName);
      setSessionId(started.sessionId);
      setInterviewMessages([createMessage("assistant", started.agentMessage)]);
      setProfileCompleteness(started.profileCompleteness);

      const status = await getInterviewStatus(started.sessionId);
      setIsReadyForGeneration(status.isReadyForGeneration);
      setInfo(`Interview started for ${started.sessionId}`);
      setStep("interview");
    } catch (err) {
      withError("Could not start interview", err);
    } finally {
      setIsStarting(false);
    }
  };

  const refreshInterviewStatus = async () => {
    if (!sessionId) {
      return;
    }

    setError("");
    setIsRefreshingStatus(true);

    try {
      const status = await getInterviewStatus(sessionId);
      setProfileCompleteness(status.profileCompleteness);
      setIsReadyForGeneration(status.isReadyForGeneration);
      setInfo(`Status refreshed. Ready: ${status.isReadyForGeneration ? "yes" : "not yet"}`);
    } catch (err) {
      withError("Could not refresh interview status", err);
    } finally {
      setIsRefreshingStatus(false);
    }
  };

  const handleInterviewSend = async (text: string) => {
    if (!sessionId) {
      return;
    }

    setError("");
    setInfo("");
    setIsSendingInterview(true);
    setInterviewMessages((prev) => [...prev, createMessage("user", text)]);

    try {
      const reply = await replyInterview(sessionId, text);
      setInterviewMessages((prev) => [...prev, createMessage("assistant", reply.agentMessage)]);
      setProfileCompleteness(reply.profileCompleteness);

      const status = await getInterviewStatus(sessionId);
      setIsReadyForGeneration(status.isReadyForGeneration);
    } catch (err) {
      withError("Interview reply failed", err);
    } finally {
      setIsSendingInterview(false);
    }
  };

  const handleComplete = async () => {
    if (!sessionId) {
      return;
    }

    setError("");
    setInfo("");
    setIsCompletingOnboarding(true);

    try {
      const completed = await completeInterview(sessionId);
      setUserProfile(completed.userProfile);
      setCurrentSelf(completed.currentSelf);

      setInfo("Current self generated. Creating future selves...");
      const exploration = await startExploration(sessionId, 3);
      const selves = exploration.futureSelves;

      setFutureSelves(selves);
      setActiveSelfId(selves[0]?.id ?? null);

      const nextHistories: Record<string, ConversationHistoryMessage[]> = {};
      for (const selfCard of selves) {
        nextHistories[selfCard.id] = [];
      }
      setHistoriesBySelf(nextHistories);

      const status = await getPipelineStatus(sessionId);
      setPipelineStatus(status);

      setInfo("Onboarding complete. Futures generated.");
      setStep("profile");
    } catch (err) {
      withError("Could not complete onboarding", err);
    } finally {
      setIsCompletingOnboarding(false);
    }
  };

  const handleRefreshPipeline = async () => {
    if (!sessionId) {
      return;
    }

    setError("");
    setIsRefreshingStatus(true);
    try {
      const status = await getPipelineStatus(sessionId);
      setPipelineStatus(status);
      setInfo(`Pipeline phase: ${status.phase} | actions: ${status.availableActions.join(", ")}`);
    } catch (err) {
      withError("Could not refresh pipeline status", err);
    } finally {
      setIsRefreshingStatus(false);
    }
  };

  const handleSendConversation = async (message: string) => {
    if (!sessionId || !activeSelfId) {
      return;
    }

    setError("");
    setInfo("");
    setIsSendingConversation(true);

    const existing = historiesBySelf[activeSelfId] || [];

    try {
      const response = await replyConversation({
        sessionId,
        selfId: activeSelfId,
        message,
        history: existing,
      });

      setHistoriesBySelf((prev) => ({
        ...prev,
        [activeSelfId]: response.history,
      }));

      setInfo(response.branchName ? `Branch: ${response.branchName}` : "Response received");
    } catch (err) {
      withError("Conversation request failed", err);
    } finally {
      setIsSendingConversation(false);
    }
  };

  const handleBranch = async (numFutures: number) => {
    if (!sessionId || !activeSelfId || !activeSelf) {
      return;
    }

    setError("");
    setInfo("");
    setIsBranching(true);

    try {
      const result = await branchConversation({
        sessionId,
        parentSelfId: activeSelfId,
        numFutures,
      });

      setFutureSelves((prev) => mergeSelves(prev, result.childSelves));

      setHistoriesBySelf((prev) => {
        const next = { ...prev };
        for (const child of result.childSelves) {
          if (!next[child.id]) {
            next[child.id] = [];
          }
        }
        return next;
      });

      if (result.childSelves.length > 0) {
        setActiveSelfId(result.childSelves[0].id);
      }

      const status = await getPipelineStatus(sessionId);
      setPipelineStatus(status);

      setInfo(`Branched from ${activeSelf.name}. Added ${result.childSelves.length} new futures.`);
    } catch (err) {
      withError("Branching failed", err);
    } finally {
      setIsBranching(false);
    }
  };

  return (
    <AppShell>
      <div className="topbar">
        <p className="brand">Tomorrow You</p>
        {sessionId ? <p className="session-chip">Session {sessionId}</p> : null}
      </div>

      {error ? <div className="banner error-banner">{error}</div> : null}
      {info ? <div className="banner info-banner">{info}</div> : null}

      {pipelineStatus ? (
        <div className="banner status-banner">
          <span>Phase: {pipelineStatus.phase}</span>
          <span>Depth: {pipelineStatus.explorationDepth}</span>
          <span>Futures: {pipelineStatus.futureSelvesCount}</span>
        </div>
      ) : null}

      {step === "landing" ? (
        <LandingScreen isLoading={isStarting} onBegin={handleStart} />
      ) : null}

      {step === "interview" ? (
        <InterviewScreen
          sessionId={sessionId}
          profileCompleteness={profileCompleteness}
          isReadyForGeneration={isReadyForGeneration}
          isSending={isSendingInterview}
          isCompleting={isCompletingOnboarding}
          messages={interviewMessages}
          onSend={handleInterviewSend}
          onRefreshStatus={refreshInterviewStatus}
          onComplete={handleComplete}
        />
      ) : null}

      {step === "profile" && userProfile && currentSelf ? (
        <ProfileRevealScreen
          profile={userProfile}
          currentSelf={currentSelf}
          onContinue={() => setStep("selection")}
        />
      ) : null}

      {step === "selection" ? (
        <SelfSelectionScreen
          futureSelves={futureSelves}
          activeSelfId={activeSelfId}
          isRefreshingStatus={isRefreshingStatus}
          onRefreshStatus={handleRefreshPipeline}
          onSelectSelf={setActiveSelfId}
          onStartConversation={() => setStep("conversation")}
        />
      ) : null}

      {step === "conversation" && activeSelfId ? (
        <ConversationScreen
          sessionId={sessionId}
          futureSelves={futureSelves}
          activeSelfId={activeSelfId}
          historiesBySelf={historiesBySelf}
          isSendingMessage={isSendingConversation}
          isBranching={isBranching}
          onChangeSelf={setActiveSelfId}
          onSendMessage={handleSendConversation}
          onBranch={handleBranch}
          onBackToSelection={() => setStep("selection")}
        />
      ) : null}
    </AppShell>
  );
}
