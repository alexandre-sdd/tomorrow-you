export type SelfType = "current" | "future";

export type MessageRole = "user" | "interviewer" | "future_self";

export type KeyFactSource = "interview" | "conversation";

export type SessionStatus =
  | "interview"
  | "profile"
  | "selection"
  | "conversation"
  | "debrief";

export type TranscriptPhase =
  | "interview"
  | "conversation"
  | "backtrack"
  | "selection"
  | "exploration";

export type TranscriptRole = "user" | "interviewer" | "future_self" | "system";

export interface UserProfile {
  id: string;
  coreValues: string[];
  fears: string[];
  hiddenTensions: string[];
  decisionStyle: string;
  selfNarrative: string;
  currentDilemma: string;
}

export interface VisualStyle {
  primaryColor: string;
  accentColor: string;
  mood: string;
  glowIntensity: number;
}

export interface SelfCard {
  id: string;
  type: SelfType;
  name: string;
  optimizationGoal: string;
  toneOfVoice: string;
  worldview: string;
  coreBelief: string;
  tradeOff: string;
  avatarPrompt: string;
  avatarUrl: string | null;
  visualStyle: VisualStyle;
  voiceId: string;

  // Tree navigation fields for multi-level branching
  parentSelfId: string | null;
  depthLevel: number;
  childrenIds: string[];
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
}

export interface KeyFact {
  id: string;
  fact: string;
  source: KeyFactSource;
  extractedAt: number;
}

export interface MemoryNode {
  id: string;
  parentId: string | null;
  branchLabel: string;
  facts: KeyFact[];
  notes: string[];
  selfCard: SelfCard | null;
  createdAt: number;
}

export interface MemoryBranch {
  name: string;
  headNodeId: string;
  parentBranchName: string | null;
}

export interface TranscriptEntry {
  id: string;
  turn: number;
  phase: TranscriptPhase;
  role: TranscriptRole;
  selfName: string | null;
  content: string;
  timestamp: number;
}

/** Lookup of every generated self by ID (tree storage) */
export type FutureSelvesFull = Record<string, SelfCard>;

/** Parent key → child self IDs (tracks what has been explored) */
export type ExplorationPaths = Record<string, string[]>;

export interface Session {
  id: string;
  status: SessionStatus;
  transcript: TranscriptEntry[];
  userProfile: UserProfile | null;
  currentSelf: SelfCard | null;
  futureSelfOptions: SelfCard[];
  selectedFutureSelf: SelfCard | null;
  memoryHead: string;
  memoryBranches: MemoryBranch[];
  memoryNodes: MemoryNode[];
  createdAt: number;
  updatedAt: number;

  // Multi-level branching tree structures
  futureSelvesFull: FutureSelvesFull;
  explorationPaths: ExplorationPaths;
}
