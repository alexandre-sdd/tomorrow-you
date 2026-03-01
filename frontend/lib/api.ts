import type { SelfCard, UserProfile } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://localhost:8000";

type Dict = Record<string, unknown>;

function asObject(value: unknown): Dict {
  return value && typeof value === "object" ? (value as Dict) : {};
}

function getStr(source: Dict, camel: string, snake?: string): string {
  const value = source[camel] ?? (snake ? source[snake] : undefined);
  return typeof value === "string" ? value : "";
}

function getNum(source: Dict, camel: string, snake?: string): number {
  const value = source[camel] ?? (snake ? source[snake] : undefined);
  return typeof value === "number" ? value : 0;
}

function getArr(source: Dict, camel: string, snake?: string): unknown[] {
  const value = source[camel] ?? (snake ? source[snake] : undefined);
  return Array.isArray(value) ? value : [];
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  const text = await response.text();
  const json = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const detail =
      (json as Dict).detail && typeof (json as Dict).detail === "string"
        ? ((json as Dict).detail as string)
        : text || `Request failed: ${response.status}`;
    throw new Error(detail);
  }

  return json as T;
}

function normalizeVisualStyle(raw: unknown): SelfCard["visualStyle"] {
  const obj = asObject(raw);
  return {
    primaryColor: getStr(obj, "primaryColor", "primary_color") || "#3F4C6B",
    accentColor: getStr(obj, "accentColor", "accent_color") || "#C8D0E0",
    mood: getStr(obj, "mood") || "calm",
    glowIntensity: getNum(obj, "glowIntensity", "glow_intensity") || 0.35,
  };
}

export function normalizeSelfCard(raw: unknown): SelfCard {
  const obj = asObject(raw);
  return {
    id: getStr(obj, "id"),
    type: (getStr(obj, "type") as SelfCard["type"]) || "future",
    name: getStr(obj, "name"),
    optimizationGoal: getStr(obj, "optimizationGoal", "optimization_goal"),
    toneOfVoice: getStr(obj, "toneOfVoice", "tone_of_voice"),
    worldview: getStr(obj, "worldview"),
    coreBelief: getStr(obj, "coreBelief", "core_belief"),
    tradeOff: getStr(obj, "tradeOff", "trade_off"),
    keyMoments: getArr(obj, "keyMoments", "key_moments") as string[],
    avatarPrompt: getStr(obj, "avatarPrompt", "avatar_prompt"),
    avatarUrl:
      (obj.avatarUrl as string | null | undefined) ??
      (obj.avatar_url as string | null | undefined) ??
      null,
    visualStyle: normalizeVisualStyle(obj.visualStyle ?? obj.visual_style),
    voiceId: getStr(obj, "voiceId", "voice_id"),
    parentSelfId: (obj.parentSelfId as string | null | undefined) ?? (obj.parent_self_id as string | null | undefined) ?? null,
    depthLevel: getNum(obj, "depthLevel", "depth_level") || 0,
    childrenIds: (getArr(obj, "childrenIds", "children_ids") as string[]) || [],
  };
}

export function normalizeUserProfile(raw: unknown): UserProfile {
  const obj = asObject(raw);
  return {
    id: getStr(obj, "id"),
    coreValues: getArr(obj, "coreValues", "core_values") as string[],
    fears: getArr(obj, "fears") as string[],
    hiddenTensions: getArr(obj, "hiddenTensions", "hidden_tensions") as string[],
    decisionStyle: getStr(obj, "decisionStyle", "decision_style"),
    selfNarrative: getStr(obj, "selfNarrative", "self_narrative"),
    currentDilemma: getStr(obj, "currentDilemma", "current_dilemma"),
  };
}

export interface InterviewStartResponse {
  sessionId: string;
  agentMessage: string;
  profileCompleteness: number;
  extractedFields: Record<string, boolean>;
}

export interface InterviewReplyResponse {
  sessionId: string;
  agentMessage: string;
  profileCompleteness: number;
  extractedFields: Record<string, boolean>;
}

export interface InterviewStatusResponse {
  sessionId: string;
  profileCompleteness: number;
  extractedFields: Record<string, boolean>;
  currentDilemma: string | null;
  isReadyForGeneration: boolean;
}

export interface InterviewCompleteResponse {
  sessionId: string;
  userProfile: UserProfile;
  currentSelf: SelfCard;
  readyForFutureGeneration: boolean;
  message: string;
}

export interface StartExplorationResponse {
  sessionId: string;
  futureSelves: SelfCard[];
  message: string;
}

export interface PipelineStatusResponse {
  sessionId: string;
  phase: string;
  status: string | null;
  availableActions: string[];
  futureSelvesCount: number;
  explorationDepth: number;
  conversationBranches: Array<{ self_id: string; name: string; depth: number }>;
}

export type ConversationHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

export interface ConversationReplyResponse {
  sessionId: string;
  selfId: string;
  branchName: string;
  reply: string;
  history: ConversationHistoryMessage[];
}

export interface BranchConversationResponse {
  sessionId: string;
  parentSelfId: string;
  parentSelfName: string;
  childSelves: SelfCard[];
  message: string;
}

export async function startInterview(sessionId: string, userName: string): Promise<InterviewStartResponse> {
  const raw = await apiFetch<Dict>("/interview/start", {
    method: "POST",
    body: JSON.stringify({ sessionId, userName }),
  });

  return {
    sessionId: getStr(raw, "sessionId", "session_id") || sessionId,
    agentMessage: getStr(raw, "agentMessage", "agent_message"),
    profileCompleteness: getNum(raw, "profileCompleteness", "profile_completeness"),
    extractedFields: (asObject(raw.extractedFields ?? raw.extracted_fields) as Record<string, boolean>) || {},
  };
}

export async function replyInterview(
  sessionId: string,
  userMessage: string,
): Promise<InterviewReplyResponse> {
  const raw = await apiFetch<Dict>("/interview/reply", {
    method: "POST",
    body: JSON.stringify({ sessionId, userMessage }),
  });

  return {
    sessionId: getStr(raw, "sessionId", "session_id") || sessionId,
    agentMessage: getStr(raw, "agentMessage", "agent_message"),
    profileCompleteness: getNum(raw, "profileCompleteness", "profile_completeness"),
    extractedFields: (asObject(raw.extractedFields ?? raw.extracted_fields) as Record<string, boolean>) || {},
  };
}

export async function getInterviewStatus(sessionId: string): Promise<InterviewStatusResponse> {
  const raw = await apiFetch<Dict>(`/interview/status?session_id=${encodeURIComponent(sessionId)}`);

  return {
    sessionId: getStr(raw, "sessionId", "session_id") || sessionId,
    profileCompleteness: getNum(raw, "profileCompleteness", "profile_completeness"),
    extractedFields: (asObject(raw.extractedFields ?? raw.extracted_fields) as Record<string, boolean>) || {},
    currentDilemma: getStr(raw, "currentDilemma", "current_dilemma") || null,
    isReadyForGeneration: Boolean(raw.isReadyForGeneration ?? raw.is_ready_for_generation),
  };
}

export async function completeInterview(
  sessionId: string,
  userConfirmedDilemma?: string,
): Promise<InterviewCompleteResponse> {
  const raw = await apiFetch<Dict>("/interview/complete", {
    method: "POST",
    body: JSON.stringify({
      sessionId,
      userConfirmedDilemma: userConfirmedDilemma || undefined,
    }),
  });

  return {
    sessionId: getStr(raw, "sessionId", "session_id") || sessionId,
    userProfile: normalizeUserProfile(raw.userProfile ?? raw.user_profile),
    currentSelf: normalizeSelfCard(raw.currentSelf ?? raw.current_self),
    readyForFutureGeneration: Boolean(raw.readyForFutureGeneration ?? raw.ready_for_future_generation),
    message: getStr(raw, "message"),
  };
}

export async function startExploration(
  sessionId: string,
  numFutures = 3,
): Promise<StartExplorationResponse> {
  const raw = await apiFetch<Dict>("/pipeline/start-exploration", {
    method: "POST",
    body: JSON.stringify({ sessionId, numFutures }),
  });

  const selvesRaw = getArr(raw, "futureSelves", "future_selves");

  return {
    sessionId: getStr(raw, "sessionId", "session_id") || sessionId,
    futureSelves: selvesRaw.map((entry) => normalizeSelfCard(entry)),
    message: getStr(raw, "message"),
  };
}

export async function getPipelineStatus(sessionId: string): Promise<PipelineStatusResponse> {
  const raw = await apiFetch<Dict>(`/pipeline/status/${encodeURIComponent(sessionId)}`);

  return {
    sessionId: getStr(raw, "sessionId", "session_id") || sessionId,
    phase: getStr(raw, "phase"),
    status: getStr(raw, "status") || null,
    availableActions: getArr(raw, "availableActions", "available_actions") as string[],
    futureSelvesCount: getNum(raw, "futureSelvesCount", "future_selves_count"),
    explorationDepth: getNum(raw, "explorationDepth", "exploration_depth"),
    conversationBranches: getArr(raw, "conversationBranches", "conversation_branches") as Array<{
      self_id: string;
      name: string;
      depth: number;
    }>,
  };
}

export async function replyConversation(params: {
  sessionId: string;
  selfId: string;
  message: string;
  history: ConversationHistoryMessage[];
}): Promise<ConversationReplyResponse> {
  const raw = await apiFetch<Dict>("/conversation/reply", {
    method: "POST",
    body: JSON.stringify({
      sessionId: params.sessionId,
      selfId: params.selfId,
      message: params.message,
      history: params.history,
    }),
  });

  const historyRaw = getArr(raw, "history");

  return {
    sessionId: getStr(raw, "sessionId", "session_id") || params.sessionId,
    selfId: getStr(raw, "selfId", "self_id") || params.selfId,
    branchName: getStr(raw, "branchName", "branch_name"),
    reply: getStr(raw, "reply"),
    history: historyRaw
      .map((item) => asObject(item))
      .filter((item) => {
        const role = getStr(item, "role");
        return role === "user" || role === "assistant";
      })
      .map((item) => ({
        role: getStr(item, "role") as "user" | "assistant",
        content: getStr(item, "content"),
      })),
  };
}

export async function branchConversation(params: {
  sessionId: string;
  parentSelfId: string;
  numFutures: number;
}): Promise<BranchConversationResponse> {
  const raw = await apiFetch<Dict>("/pipeline/branch-conversation", {
    method: "POST",
    body: JSON.stringify({
      sessionId: params.sessionId,
      parentSelfId: params.parentSelfId,
      numFutures: params.numFutures,
    }),
  });

  return {
    sessionId: getStr(raw, "sessionId", "session_id") || params.sessionId,
    parentSelfId: getStr(raw, "parentSelfId", "parent_self_id") || params.parentSelfId,
    parentSelfName: getStr(raw, "parentSelfName", "parent_self_name"),
    childSelves: getArr(raw, "childSelves", "child_selves").map((entry) => normalizeSelfCard(entry)),
    message: getStr(raw, "message"),
  };
}
