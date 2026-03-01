import type {
  ExplorationPaths,
  FutureSelvesFull,
  MemoryBranch,
  MemoryNode,
  SelfCard,
  Session,
  TranscriptEntry,
  UserProfile,
} from "./types";

const baseTimestamp = 1772294400;

export const mockUserProfile: UserProfile = {
  id: "user_nyc_singapore_001",
  coreValues: [
    "family stability",
    "career growth",
    "financial security",
    "building a strong life with my wife",
  ],
  fears: [
    "regretting a missed career opportunity",
    "damaging the balance of my marriage",
    "feeling isolated far from home",
    "choosing comfort over long-term growth",
  ],
  hiddenTensions: [
    "I want rapid career progression, but I also want emotional closeness and routine",
    "I see myself as ambitious, but I do not want success to come at the expense of family life",
    "I am drawn to the idea of reinvention abroad, but I am afraid of losing my support system",
  ],
  decisionStyle:
    "Analytical and forward-looking, but much slower and more conflicted when a decision affects family life.",
  selfNarrative:
    "I am a high-performing young professional who has built strong momentum in New York, but I increasingly judge success by the quality of the life I build with my wife, not just by title or salary.",
  currentDilemma:
    "Should I accept a promotion that moves me from New York to Singapore, knowing it could accelerate my career but significantly reshape my marriage, my routines, and the life we have started building together?",
};

export const mockCurrentSelf: SelfCard = {
  id: "self_current_001",
  type: "current",
  name: "Current Self",
  optimizationGoal:
    "Balance career growth, financial upside, marital stability, and long-term life coherence.",
  toneOfVoice:
    "Measured, reflective, articulate, slightly tense, careful with conclusions.",
  worldview:
    "The best decisions are the ones that create momentum without damaging the parts of life that matter most.",
  coreBelief:
    "Success only means something if it fits the life I actually want to live with the person I chose.",
  tradeOff:
    "By trying to preserve balance and optionality, I risk staying in uncertainty for too long and avoiding a decisive move.",
  avatarPrompt:
    "A realistic 28-year-old professional man living in New York, thoughtful expression, modern understated business-casual clothing, subtle signs of internal tension, polished urban aesthetic, cinematic portrait, emotionally grounded, premium product style",
  avatarUrl: null,
  visualStyle: {
    primaryColor: "#1F3A5F",
    accentColor: "#D6E4F0",
    mood: "calm",
    glowIntensity: 0.34,
  },
  voiceId: "voice_current_placeholder",
  parentSelfId: null,
  depthLevel: 0,
  childrenIds: ["self_future_singapore_001", "self_future_nyc_001"],
};

export const mockSingaporeSelf: SelfCard = {
  id: "self_future_singapore_001",
  type: "future",
  name: "Self Who Took the Singapore Move",
  optimizationGoal:
    "Maximize career acceleration, international exposure, leadership trajectory, and long-term upside.",
  toneOfVoice: "Calm, confident, precise, more decisive, emotionally controlled.",
  worldview:
    "Some decisions feel disruptive in the moment, but they become the moves that define your life if you fully grow into them.",
  coreBelief:
    "You do not become who you could be by staying where everything already fits.",
  tradeOff:
    "I gained speed, status, and reinvention, but I gave up familiarity, relational ease, and some short-term emotional safety.",
  avatarPrompt:
    "A realistic 33-year-old professional man living in Singapore after an international promotion, sharper presence, elegant tailored clothing, warm city lights in the background, confident but slightly more distant expression, global executive energy, premium cinematic portrait, sophisticated and emotionally restrained",
  avatarUrl: null,
  visualStyle: {
    primaryColor: "#0E5E6F",
    accentColor: "#D8F3DC",
    mood: "elevated",
    glowIntensity: 0.58,
  },
  voiceId: "voice_future_singapore_placeholder",
  parentSelfId: null,
  depthLevel: 1,
  childrenIds: [],
};

export const mockSelfCards: SelfCard[] = [mockCurrentSelf, mockSingaporeSelf];

export const mockStayInNYCSelf: SelfCard = {
  id: "self_future_nyc_001",
  type: "future",
  name: "Self Who Stayed in New York",
  optimizationGoal:
    "Preserve relational stability, continuity, local momentum, and a more grounded long-term life path.",
  toneOfVoice:
    "Warm, steady, thoughtful, reassuring, emotionally available.",
  worldview:
    "A good life is not always the fastest one; sometimes depth comes from staying with what matters and building it well.",
  coreBelief: "Not every meaningful life is built through dramatic moves.",
  tradeOff:
    "I kept closeness, continuity, and a stronger sense of home, but I may always wonder how much further I could have gone.",
  avatarPrompt:
    "A realistic 33-year-old professional man still living in New York, grounded and emotionally present, refined but relaxed style, warm apartment or city evening lighting, stable and thoughtful expression, premium cinematic portrait, intimate and human",
  avatarUrl: null,
  visualStyle: {
    primaryColor: "#7A4E2D",
    accentColor: "#F3E9DC",
    mood: "warm",
    glowIntensity: 0.42,
  },
  voiceId: "voice_future_nyc_placeholder",
  parentSelfId: null,
  depthLevel: 1,
  childrenIds: [],
};

export const mockFutureSelfOptions: SelfCard[] = [
  mockSingaporeSelf,
  mockStayInNYCSelf,
];

export const mockFutureSelvesFull: FutureSelvesFull = {
  [mockSingaporeSelf.id]: mockSingaporeSelf,
  [mockStayInNYCSelf.id]: mockStayInNYCSelf,
};

export const mockExplorationPaths: ExplorationPaths = {
  root: [mockSingaporeSelf.id, mockStayInNYCSelf.id],
};

export const mockTranscript: TranscriptEntry[] = [
  {
    id: "te_001",
    turn: 1,
    phase: "interview",
    role: "system",
    selfName: null,
    content: "Interview complete. Profile extracted.",
    timestamp: baseTimestamp,
  },
  {
    id: "te_002",
    turn: 2,
    phase: "selection",
    role: "system",
    selfName: null,
    content:
      "Future self options generated: Self Who Took the Singapore Move, Self Who Stayed in New York.",
    timestamp: baseTimestamp + 10,
  },
];

export const mockMemoryNodes: MemoryNode[] = [
  {
    id: "node_root_profile",
    parentId: null,
    branchLabel: "root",
    facts: [
      {
        id: "fact_root_001",
        fact: "Core values include family stability, career growth, and financial security.",
        source: "interview",
        extractedAt: baseTimestamp,
      },
      {
        id: "fact_root_002",
        fact: "Current dilemma is a potential move from New York to Singapore for a promotion.",
        source: "interview",
        extractedAt: baseTimestamp,
      },
      {
        id: "fact_root_003",
        fact: "Strong concern about protecting marriage quality while pursuing ambition.",
        source: "interview",
        extractedAt: baseTimestamp,
      },
    ],
    notes: [
      "Root node created from profile extraction.",
      "Seed state before future-self branch selection.",
    ],
    selfCard: null,
    createdAt: baseTimestamp,
  },
  {
    id: "node_branch_singapore_001",
    parentId: "node_root_profile",
    branchLabel: "self-who-took-the-singapore-move",
    facts: [
      {
        id: "fact_sg_001",
        fact: "This branch optimizes for acceleration, reinvention, and leadership upside.",
        source: "interview",
        extractedAt: baseTimestamp + 20,
      },
    ],
    notes: ["Initial branch node for Singapore path."],
    selfCard: mockSingaporeSelf,
    createdAt: baseTimestamp + 20,
  },
  {
    id: "node_branch_nyc_001",
    parentId: "node_root_profile",
    branchLabel: "self-who-stayed-in-new-york",
    facts: [
      {
        id: "fact_nyc_001",
        fact: "This branch optimizes for relational continuity, emotional presence, and grounded growth.",
        source: "interview",
        extractedAt: baseTimestamp + 20,
      },
    ],
    notes: ["Initial branch node for NYC path."],
    selfCard: mockStayInNYCSelf,
    createdAt: baseTimestamp + 20,
  },
];

export const mockMemoryBranches: MemoryBranch[] = [
  {
    name: "root",
    headNodeId: "node_root_profile",
    parentBranchName: null,
  },
  {
    name: "self-who-took-the-singapore-move",
    headNodeId: "node_branch_singapore_001",
    parentBranchName: "root",
  },
  {
    name: "self-who-stayed-in-new-york",
    headNodeId: "node_branch_nyc_001",
    parentBranchName: "root",
  },
];

export const mockSession: Session = {
  id: mockUserProfile.id,
  status: "selection",
  transcript: mockTranscript,
  userProfile: mockUserProfile,
  currentSelf: mockCurrentSelf,
  futureSelfOptions: mockFutureSelfOptions,
  selectedFutureSelf: null,
  memoryHead: "root",
  memoryBranches: mockMemoryBranches,
  memoryNodes: mockMemoryNodes,
  createdAt: baseTimestamp,
  updatedAt: baseTimestamp + 20,
  futureSelvesFull: mockFutureSelvesFull,
  explorationPaths: mockExplorationPaths,
};
