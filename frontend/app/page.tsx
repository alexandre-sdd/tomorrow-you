"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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
  synthesizeConversationAudio,
  synthesizeInterviewAudio,
  transcribeConversationAudio,
  transcribeInterviewAudio,
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
  const [isRecordingInterview, setIsRecordingInterview] = useState(false);
  const [isTranscribingInterview, setIsTranscribingInterview] = useState(false);
  const [isSynthesizingInterview, setIsSynthesizingInterview] = useState(false);
  const [isPlayingInterviewAudio, setIsPlayingInterviewAudio] = useState(false);
  const [lastReplyAudioBlob, setLastReplyAudioBlob] = useState<Blob | null>(null);
  const [lastAssistantReplyText, setLastAssistantReplyText] = useState("");
  const [isSendingConversation, setIsSendingConversation] = useState(false);
  const [isBranching, setIsBranching] = useState(false);
  const [isRecordingConversation, setIsRecordingConversation] = useState(false);
  const [isTranscribingConversation, setIsTranscribingConversation] = useState(false);
  const [isSynthesizingConversation, setIsSynthesizingConversation] = useState(false);
  const [isPlayingConversationAudio, setIsPlayingConversationAudio] = useState(false);
  const [lastConversationReplyAudioBlob, setLastConversationReplyAudioBlob] = useState<Blob | null>(null);
  const [lastConversationReplyText, setLastConversationReplyText] = useState("");

  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const interviewRecorderRef = useRef<MediaRecorder | null>(null);
  const interviewStreamRef = useRef<MediaStream | null>(null);
  const interviewChunksRef = useRef<Blob[]>([]);
  const interviewAudioRef = useRef<HTMLAudioElement | null>(null);
  const interviewAudioUrlRef = useRef<string | null>(null);
  const interviewPressActiveRef = useRef(false);
  const interviewRecorderStartingRef = useRef(false);
  const conversationRecorderRef = useRef<MediaRecorder | null>(null);
  const conversationStreamRef = useRef<MediaStream | null>(null);
  const conversationChunksRef = useRef<Blob[]>([]);
  const conversationAudioRef = useRef<HTMLAudioElement | null>(null);
  const conversationAudioUrlRef = useRef<string | null>(null);
  const conversationPressActiveRef = useRef(false);
  const conversationRecorderStartingRef = useRef(false);

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

  const stopInterviewPlayback = () => {
    if (interviewAudioRef.current) {
      interviewAudioRef.current.pause();
      interviewAudioRef.current.currentTime = 0;
      interviewAudioRef.current = null;
    }
    if (interviewAudioUrlRef.current) {
      URL.revokeObjectURL(interviewAudioUrlRef.current);
      interviewAudioUrlRef.current = null;
    }
    setIsPlayingInterviewAudio(false);
  };

  const stopConversationPlayback = () => {
    if (conversationAudioRef.current) {
      conversationAudioRef.current.pause();
      conversationAudioRef.current.currentTime = 0;
      conversationAudioRef.current = null;
    }
    if (conversationAudioUrlRef.current) {
      URL.revokeObjectURL(conversationAudioUrlRef.current);
      conversationAudioUrlRef.current = null;
    }
    setIsPlayingConversationAudio(false);
  };

  const releaseInterviewMic = () => {
    interviewPressActiveRef.current = false;
    interviewRecorderStartingRef.current = false;
    if (interviewStreamRef.current) {
      for (const track of interviewStreamRef.current.getTracks()) {
        track.stop();
      }
      interviewStreamRef.current = null;
    }
    interviewRecorderRef.current = null;
    interviewChunksRef.current = [];
    setIsRecordingInterview(false);
  };

  const releaseConversationMic = () => {
    conversationPressActiveRef.current = false;
    conversationRecorderStartingRef.current = false;
    if (conversationStreamRef.current) {
      for (const track of conversationStreamRef.current.getTracks()) {
        track.stop();
      }
      conversationStreamRef.current = null;
    }
    conversationRecorderRef.current = null;
    conversationChunksRef.current = [];
    setIsRecordingConversation(false);
  };

  const playInterviewAudioBlob = async (blob: Blob) => {
    stopInterviewPlayback();

    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    interviewAudioRef.current = audio;
    interviewAudioUrlRef.current = url;

    audio.onended = () => {
      setIsPlayingInterviewAudio(false);
    };
    audio.onerror = () => {
      setIsPlayingInterviewAudio(false);
    };

    await audio.play();
    setIsPlayingInterviewAudio(true);
  };

  const playConversationAudioBlob = async (blob: Blob) => {
    stopConversationPlayback();

    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    conversationAudioRef.current = audio;
    conversationAudioUrlRef.current = url;

    audio.onended = () => {
      setIsPlayingConversationAudio(false);
    };
    audio.onerror = () => {
      setIsPlayingConversationAudio(false);
    };

    await audio.play();
    setIsPlayingConversationAudio(true);
  };

  const synthesizeAndPlayInterviewReply = async (replyText: string) => {
    if (!sessionId || !replyText.trim()) {
      return;
    }

    setLastAssistantReplyText(replyText);
    setIsSynthesizingInterview(true);
    try {
      const audioBlob = await synthesizeInterviewAudio({
        sessionId,
        text: replyText,
      });
      setLastReplyAudioBlob(audioBlob);
      await playInterviewAudioBlob(audioBlob);
    } catch (err) {
      withError("Reply generated but voice playback failed", err);
    } finally {
      setIsSynthesizingInterview(false);
    }
  };

  const synthesizeAndPlayConversationReply = async (
    replyText: string,
    selfId: string,
  ) => {
    if (!sessionId || !replyText.trim()) {
      return;
    }

    setLastConversationReplyText(replyText);
    setIsSynthesizingConversation(true);
    try {
      const audioBlob = await synthesizeConversationAudio({
        sessionId,
        selfId,
        text: replyText,
      });
      setLastConversationReplyAudioBlob(audioBlob);
      await playConversationAudioBlob(audioBlob);
    } catch (err) {
      withError("Conversation reply generated but voice playback failed", err);
    } finally {
      setIsSynthesizingConversation(false);
    }
  };

  useEffect(() => {
    return () => {
      stopInterviewPlayback();
      releaseInterviewMic();
      stopConversationPlayback();
      releaseConversationMic();
    };
  }, []);

  useEffect(() => {
    stopConversationPlayback();
    releaseConversationMic();
    setLastConversationReplyAudioBlob(null);
    setLastConversationReplyText("");
  }, [activeSelfId]);

  const handleStart = async (params: { sessionId: string; userName: string }) => {
    setError("");
    setInfo("");
    setIsStarting(true);
    interviewPressActiveRef.current = false;
    stopInterviewPlayback();
    releaseInterviewMic();
    setLastReplyAudioBlob(null);
    setLastAssistantReplyText("");

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

  const handleInterviewSend = async (
    text: string,
    options: { speakReply?: boolean } = {},
  ) => {
    if (!sessionId) {
      return;
    }

    setError("");
    setInfo("");
    setIsSendingInterview(true);
    setInterviewMessages((prev) => [...prev, createMessage("user", text)]);

    let assistantMessage = "";
    try {
      const reply = await replyInterview(sessionId, text);
      setInterviewMessages((prev) => [...prev, createMessage("assistant", reply.agentMessage)]);
      assistantMessage = reply.agentMessage;
      setLastAssistantReplyText(reply.agentMessage);
      setProfileCompleteness(reply.profileCompleteness);

      const status = await getInterviewStatus(sessionId);
      setIsReadyForGeneration(status.isReadyForGeneration);
    } catch (err) {
      withError("Interview reply failed", err);
    } finally {
      setIsSendingInterview(false);
    }

    if (assistantMessage && options.speakReply !== false) {
      await synthesizeAndPlayInterviewReply(assistantMessage);
    }
  };

  const handleStopInterviewRecording = async () => {
    interviewPressActiveRef.current = false;
    const activeRecorder = interviewRecorderRef.current;
    if (activeRecorder && activeRecorder.state !== "inactive") {
      activeRecorder.stop();
    }
  };

  const handleStartInterviewRecording = async () => {
    interviewPressActiveRef.current = true;
    if (
      !sessionId
      || isRecordingInterview
      || interviewRecorderStartingRef.current
      || isTranscribingInterview
      || isSynthesizingInterview
      || isSendingInterview
      || isCompletingOnboarding
    ) {
      if (!isRecordingInterview) {
        interviewPressActiveRef.current = false;
      }
      return;
    }

    setError("");
    setInfo("");

    if (typeof window === "undefined" || !navigator?.mediaDevices?.getUserMedia) {
      interviewPressActiveRef.current = false;
      setError("Microphone is not available in this browser.");
      return;
    }

    interviewRecorderStartingRef.current = true;
    try {
      stopInterviewPlayback();

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      interviewStreamRef.current = stream;

      const mimeTypeCandidates = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
      ];
      const pickedMimeType = mimeTypeCandidates.find((candidate) =>
        typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(candidate),
      );

      const recorder = pickedMimeType
        ? new MediaRecorder(stream, { mimeType: pickedMimeType })
        : new MediaRecorder(stream);

      interviewRecorderRef.current = recorder;
      interviewChunksRef.current = [];

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          interviewChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const chunks = interviewChunksRef.current;
        interviewChunksRef.current = [];
        setIsRecordingInterview(false);

        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        releaseInterviewMic();

        if (blob.size === 0) {
          setError("No audio captured. Please try again.");
          return;
        }

        setIsTranscribingInterview(true);
        try {
          const transcription = await transcribeInterviewAudio({
            sessionId,
            audioBlob: blob,
          });
          const transcript = transcription.transcriptText.trim();
          if (!transcript) {
            setError("Couldn't transcribe that turn. Please try again.");
            return;
          }

          await handleInterviewSend(transcript, { speakReply: true });
        } catch (err) {
          withError("Voice transcription failed", err);
        } finally {
          setIsTranscribingInterview(false);
        }
      };

      recorder.onerror = () => {
        releaseInterviewMic();
        setError("Recording failed. Please try again.");
      };

      recorder.start();
      setIsRecordingInterview(true);
      setInfo("Recording... release mic to send.");
      if (!interviewPressActiveRef.current && recorder.state !== "inactive") {
        recorder.stop();
      }
    } catch (err) {
      releaseInterviewMic();
      withError(
        "Microphone permission is required for voice interview turns.",
        err,
      );
    } finally {
      interviewRecorderStartingRef.current = false;
    }
  };

  const handleReplayInterviewAudio = async () => {
    if (!lastReplyAudioBlob && !lastAssistantReplyText.trim()) {
      return;
    }

    setError("");
    try {
      if (lastReplyAudioBlob) {
        await playInterviewAudioBlob(lastReplyAudioBlob);
        return;
      }
      await synthesizeAndPlayInterviewReply(lastAssistantReplyText);
    } catch (err) {
      withError("Could not play the latest reply audio", err);
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

  const handleSendConversation = async (
    message: string,
    options: { speakReply?: boolean } = {},
  ) => {
    if (!sessionId || !activeSelfId) {
      return;
    }

    setError("");
    setInfo("");
    setIsSendingConversation(true);

    const targetSelfId = activeSelfId;
    const existing = historiesBySelf[targetSelfId] || [];
    let assistantMessage = "";

    try {
      const response = await replyConversation({
        sessionId,
        selfId: targetSelfId,
        message,
        history: existing,
      });

      setHistoriesBySelf((prev) => ({
        ...prev,
        [targetSelfId]: response.history,
      }));
      assistantMessage = response.reply;
      setLastConversationReplyText(response.reply);

      setInfo(response.branchName ? `Branch: ${response.branchName}` : "Response received");
    } catch (err) {
      withError("Conversation request failed", err);
    } finally {
      setIsSendingConversation(false);
    }

    if (assistantMessage && options.speakReply !== false) {
      await synthesizeAndPlayConversationReply(assistantMessage, targetSelfId);
    }
  };

  const handleStopConversationRecording = async () => {
    conversationPressActiveRef.current = false;
    const activeRecorder = conversationRecorderRef.current;
    if (activeRecorder && activeRecorder.state !== "inactive") {
      activeRecorder.stop();
    }
  };

  const handleStartConversationRecording = async () => {
    conversationPressActiveRef.current = true;
    if (
      !sessionId
      || !activeSelfId
      || isRecordingConversation
      || conversationRecorderStartingRef.current
      || isTranscribingConversation
      || isSynthesizingConversation
      || isSendingConversation
      || isBranching
    ) {
      if (!isRecordingConversation) {
        conversationPressActiveRef.current = false;
      }
      return;
    }

    setError("");
    setInfo("");

    if (typeof window === "undefined" || !navigator?.mediaDevices?.getUserMedia) {
      conversationPressActiveRef.current = false;
      setError("Microphone is not available in this browser.");
      return;
    }

    conversationRecorderStartingRef.current = true;
    try {
      stopConversationPlayback();

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      conversationStreamRef.current = stream;

      const mimeTypeCandidates = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
      ];
      const pickedMimeType = mimeTypeCandidates.find((candidate) =>
        typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(candidate),
      );

      const recorder = pickedMimeType
        ? new MediaRecorder(stream, { mimeType: pickedMimeType })
        : new MediaRecorder(stream);

      conversationRecorderRef.current = recorder;
      conversationChunksRef.current = [];

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          conversationChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const chunks = conversationChunksRef.current;
        conversationChunksRef.current = [];
        setIsRecordingConversation(false);

        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        releaseConversationMic();

        if (blob.size === 0) {
          setError("No audio captured. Please try again.");
          return;
        }

        const currentSelfId = activeSelfId;
        if (!currentSelfId) {
          setError("No active future self selected.");
          return;
        }

        setIsTranscribingConversation(true);
        try {
          const transcription = await transcribeConversationAudio({
            sessionId,
            selfId: currentSelfId,
            audioBlob: blob,
          });
          const transcript = transcription.transcriptText.trim();
          if (!transcript) {
            setError("Couldn't transcribe that turn. Please try again.");
            return;
          }

          await handleSendConversation(transcript, { speakReply: true });
        } catch (err) {
          withError("Conversation voice transcription failed", err);
        } finally {
          setIsTranscribingConversation(false);
        }
      };

      recorder.onerror = () => {
        releaseConversationMic();
        setError("Recording failed. Please try again.");
      };

      recorder.start();
      setIsRecordingConversation(true);
      setInfo("Recording conversation... release mic to send.");
      if (!conversationPressActiveRef.current && recorder.state !== "inactive") {
        recorder.stop();
      }
    } catch (err) {
      releaseConversationMic();
      withError("Microphone permission is required for voice conversation turns.", err);
    } finally {
      conversationRecorderStartingRef.current = false;
    }
  };

  const handleReplayConversationAudio = async () => {
    if (!activeSelfId) {
      return;
    }
    if (!lastConversationReplyAudioBlob && !lastConversationReplyText.trim()) {
      return;
    }

    setError("");
    try {
      if (lastConversationReplyAudioBlob) {
        await playConversationAudioBlob(lastConversationReplyAudioBlob);
        return;
      }
      await synthesizeAndPlayConversationReply(lastConversationReplyText, activeSelfId);
    } catch (err) {
      withError("Could not play the latest conversation reply audio", err);
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
          isRecording={isRecordingInterview}
          isTranscribing={isTranscribingInterview}
          isSynthesizing={isSynthesizingInterview}
          isPlaying={isPlayingInterviewAudio}
          canReplayLastAudio={Boolean(lastReplyAudioBlob || lastAssistantReplyText.trim())}
          messages={interviewMessages}
          onSend={handleInterviewSend}
          onRefreshStatus={refreshInterviewStatus}
          onComplete={handleComplete}
          onStartRecording={handleStartInterviewRecording}
          onStopRecording={handleStopInterviewRecording}
          onReplayLastAudio={handleReplayInterviewAudio}
        />
      ) : null}

      {step === "profile" && userProfile && currentSelf ? (
        <ProfileRevealScreen
          sessionId={sessionId}
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
          isRecording={isRecordingConversation}
          isTranscribing={isTranscribingConversation}
          isSynthesizing={isSynthesizingConversation}
          isPlaying={isPlayingConversationAudio}
          canReplayLastAudio={Boolean(lastConversationReplyAudioBlob || lastConversationReplyText.trim())}
          onChangeSelf={setActiveSelfId}
          onSendMessage={handleSendConversation}
          onBranch={handleBranch}
          onStartRecording={handleStartConversationRecording}
          onStopRecording={handleStopConversationRecording}
          onReplayLastAudio={handleReplayConversationAudio}
          onBackToSelection={() => setStep("selection")}
        />
      ) : null}
    </AppShell>
  );
}
