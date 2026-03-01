"use client";

import { ChatPanel } from "@/components/ChatPanel";
import { InputBar } from "@/components/InputBar";
import { ScreenHeader } from "@/components/ScreenHeader";

interface InterviewMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
}

interface InterviewScreenProps {
  sessionId: string;
  profileCompleteness: number;
  isReadyForGeneration: boolean;
  isSending: boolean;
  isCompleting: boolean;
  isRecording: boolean;
  isTranscribing: boolean;
  isSynthesizing: boolean;
  isPlaying: boolean;
  canReplayLastAudio: boolean;
  messages: InterviewMessage[];
  onSend: (text: string) => Promise<void>;
  onRefreshStatus: () => Promise<void>;
  onComplete: () => Promise<void>;
  onStartRecording: () => Promise<void>;
  onStopRecording: () => Promise<void>;
  onReplayLastAudio: () => Promise<void>;
}

export function InterviewScreen({
  sessionId,
  profileCompleteness,
  isReadyForGeneration,
  isSending,
  isCompleting,
  isRecording,
  isTranscribing,
  isSynthesizing,
  isPlaying,
  canReplayLastAudio,
  messages,
  onSend,
  onRefreshStatus,
  onComplete,
  onStartRecording,
  onStopRecording,
  onReplayLastAudio,
}: InterviewScreenProps) {
  const completionPct = profileCompleteness * 100;
  const canComplete = completionPct >= 50;
  const isVoiceBusy = isTranscribing || isSynthesizing;
  const inputDisabled = isSending || isCompleting || isVoiceBusy || isRecording;
  const recordButtonLabel = isRecording ? "■" : "🎙";
  const recordButtonTitle = isRecording ? "Release to stop" : "Hold to talk";
  const voiceStatus = isRecording
    ? "Recording..."
    : isTranscribing
      ? "Transcribing..."
      : isSynthesizing
        ? "Synthesizing reply..."
        : isPlaying
          ? "Playing reply..."
          : "Voice ready";

  return (
    <section className="stack-screen">
      <ScreenHeader
        eyebrow={`Session ${sessionId}`}
        title="Your Multiverse Interview"
        subtitle="Answer naturally. The interviewer builds your profile in real time."
      />

      <div className="surface-card status-card">
        <div className="status-row">
          <span>Profile completeness</span>
          <strong>{completionPct.toFixed(1)}%</strong>
        </div>
        <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(completionPct)}>
          <span style={{ width: `${Math.max(4, Math.round(completionPct))}%` }} />
        </div>
        <div className="status-actions">
          <button type="button" className="ghost-button" onClick={onRefreshStatus} disabled={isSending || isCompleting}>
            Refresh status
          </button>
          <button
            type="button"
            onClick={onComplete}
            disabled={isSending || isCompleting || !canComplete}
            title={canComplete ? "" : "Complete unlocks at 50% profile completeness"}
          >
            {isCompleting ? "Generating current self..." : "Complete and generate futures"}
          </button>
        </div>
        <div className="voice-actions">
          <button
            type="button"
            className="ghost-button"
            onClick={onReplayLastAudio}
            disabled={!canReplayLastAudio || isRecording || isTranscribing}
          >
            Play last reply
          </button>
          <p className="voice-status">{voiceStatus}</p>
        </div>
        {!canComplete ? (
          <p className="status-hint">
            Reach 50.0% to unlock completion.
          </p>
        ) : null}
        {isReadyForGeneration ? (
          <p className="status-hint">
            Interview agent also marks profile as ready.
          </p>
        ) : null}
      </div>

      <ChatPanel
        messages={messages}
        emptyText="Interview will appear here after session starts."
      />

      <InputBar
        placeholder="Type your response..."
        submitLabel={isSending ? "Sending..." : "Send"}
        disabled={inputDisabled}
        secondaryActionLabel={recordButtonLabel}
        secondaryActionTitle={recordButtonTitle}
        secondaryActionClassName={isRecording ? "recording-button icon-button" : "ghost-button icon-button"}
        secondaryActionDisabled={isCompleting || isSending || isVoiceBusy}
        onSecondaryActionPressStart={onStartRecording}
        onSecondaryActionPressEnd={onStopRecording}
        onSubmit={onSend}
      />
    </section>
  );
}
