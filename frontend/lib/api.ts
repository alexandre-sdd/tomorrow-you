import type { SelfCard, UserProfile } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://localhost:8000";

type UnknownRecord = Record<string, unknown>;

export interface InterviewStartResult {
  sessionId: string;
  agentMessage: string;
  profileCompleteness: number;
}

export interface InterviewReplyResult {
  sessionId: string;
  agentMessage: string;
  profileCompleteness: number;
}

export interface InterviewCompleteResult {
  sessionId: string;
  userProfile: UserProfile;
  currentSelf: SelfCard;
  readyForFutureGeneration: boolean;
  message: string;
}

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === "object" ? (value as UnknownRecord) : {};
}

function readString(record: UnknownRecord, ...keys: string[]): string {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return "";
}

function readNumber(record: UnknownRecord, ...keys: string[]): number {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
  }
  return 0;
}

async function apiRequest(path: string, payload: UnknownRecord): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      const bodyRecord = asRecord(body);
      const message = readString(bodyRecord, "detail", "message", "error");
      if (message) {
        detail = message;
      }
    } catch {
      // no-op
    }
    throw new Error(detail);
  }

  return response.json();
}

export async function startInterview(sessionId: string, userName = "User"): Promise<InterviewStartResult> {
  const raw = asRecord(
    await apiRequest("/interview/start", {
      sessionId,
      userName,
    }),
  );
  return {
    sessionId: readString(raw, "sessionId", "session_id") || sessionId,
    agentMessage:
      readString(raw, "agentMessage", "agent_message") ||
      "Let us begin. What is most in tension for you right now?",
    profileCompleteness: readNumber(raw, "profileCompleteness", "profile_completeness"),
  };
}

export async function replyInterview(sessionId: string, userMessage: string): Promise<InterviewReplyResult> {
  const raw = asRecord(
    await apiRequest("/interview/reply", {
      sessionId,
      userMessage,
      stream: false,
    }),
  );
  return {
    sessionId: readString(raw, "sessionId", "session_id") || sessionId,
    agentMessage:
      readString(raw, "agentMessage", "agent_message") ||
      "Could you tell me more?",
    profileCompleteness: readNumber(raw, "profileCompleteness", "profile_completeness"),
  };
}

export async function completeInterview(sessionId: string): Promise<InterviewCompleteResult> {
  const raw = asRecord(
    await apiRequest("/interview/complete", {
      sessionId,
    }),
  );

  const rawProfile = asRecord(raw.userProfile ?? raw.user_profile);
  const rawCurrentSelf = asRecord(raw.currentSelf ?? raw.current_self);

  return {
    sessionId: readString(raw, "sessionId", "session_id") || sessionId,
    userProfile: rawProfile as unknown as UserProfile,
    currentSelf: rawCurrentSelf as unknown as SelfCard,
    readyForFutureGeneration:
      Boolean(raw.readyForFutureGeneration ?? raw.ready_for_future_generation),
    message: readString(raw, "message") || "Interview completed.",
  };
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}
