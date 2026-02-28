# Shared — Data Contracts & Schemas

## Purpose
The single source of truth for all data shapes that cross the frontend-backend boundary. Every API request/response, every stored object, and every internal data structure is defined here. This prevents frontend and backend from drifting apart.

## Why This Exists
The architecture.md critique identified that there were no defined data contracts between layers. Without explicit schemas, the frontend might expect `userName` while the backend sends `user_name`, or the profile might have different fields depending on which endpoint generated it. This folder fixes that.

## Core Schemas

### `UserProfile`
The structured identity extracted from the interview.
```
UserProfile {
  id: string
  coreValues: string[]          // what the user cares about most
  fears: string[]               // what they're afraid of
  hiddenTensions: string[]      // contradictions in their values/desires
  decisionStyle: string         // how they typically make decisions
  selfNarrative: string         // the story they tell about themselves
  currentDilemma: string        // the decision they're facing right now
}
```

### `SelfCard`
A persona card — used for both the current self and future selves.
```
SelfCard {
  id: string
  type: "current" | "future"
  name: string                  // e.g. "The Architect", "The Wanderer"
  optimizationGoal: string      // what this self optimizes for
  toneOfVoice: string           // how they speak
  worldview: string             // how they see the world
  coreBelief: string            // their fundamental belief
  tradeOff: string              // what they sacrifice
  avatarPrompt: string          // description for AI image generation
  avatarUrl: string | null      // URL/path to generated avatar image (null until generated)
  visualStyle: {                // drives UI theming around the avatar
    primaryColor: string
    accentColor: string
    mood: string                // e.g. "warm", "sharp", "ethereal"
    glowIntensity: number       // 0-1, UI glow effect around avatar
  }
  voiceId: string               // ElevenLabs voice ID
}
```

### `Message`
A single conversation turn.
```
Message {
  id: string
  role: "user" | "interviewer" | "future_self"
  content: string
  timestamp: number
}
```

### `KeyFact`
An extracted fact from conversation, stored in memory.
```
KeyFact {
  id: string
  fact: string                  // e.g. "User left their job 3 months ago"
  source: "interview" | "conversation"
  extractedAt: number
}
```

### `MemoryNode`
A single node in the memory tree — a snapshot of extracted knowledge at a branch point.
```
MemoryNode {
  id: string
  parentId: string | null       // parent node (null for root)
  branchLabel: string           // e.g. "root", "The Architect", "deeper-conversation"
  facts: KeyFact[]              // extracted facts at this point
  notes: string[]               // free-form observations
  selfCard: SelfCard | null     // which self this branch explores (null for root)
  createdAt: number
}
```

### `MemoryBranch`
A pointer to the latest node on a branch path (like a git branch ref).
```
MemoryBranch {
  name: string                  // e.g. "the-architect", "the-wanderer"
  headNodeId: string            // latest MemoryNode on this branch
  parentBranchName: string | null
}
```

### `Session`
The full session state. Transcript is linear (append-only). Memory is a tree (branches at decision points).
```
Session {
  id: string
  status: "interview" | "profile" | "selection" | "conversation" | "debrief"
  transcript: TranscriptEntry[] // linear log of ALL events, never branched or deleted
  userProfile: UserProfile | null
  currentSelf: SelfCard | null
  futureSelfOptions: SelfCard[]
  selectedFutureSelf: SelfCard | null
  memoryHead: string            // current branch name (like git HEAD)
  memoryBranches: MemoryBranch[]
  memoryNodes: MemoryNode[]
  createdAt: number
  updatedAt: number
}
```

### `TranscriptEntry`
A single entry in the linear transcript log. Captures conversations AND navigation events.
```
TranscriptEntry {
  id: string
  turn: number                  // monotonically increasing
  phase: "interview" | "conversation" | "backtrack" | "selection"
  role: "user" | "interviewer" | "future_self" | "system"
  selfName: string | null       // which future self (null during interview)
  content: string
  timestamp: number
}
```

## How This Is Used
- **Backend (Python)**: These schemas map to Pydantic models in `backend/models/`
- **Frontend (TypeScript)**: These schemas map to TypeScript types in `frontend/types/`
- This README is the canonical reference — if the Pydantic models and TS types ever disagree, this file is correct

## TODO
- [ ] Create Python Pydantic models matching these schemas
- [ ] Create TypeScript type definitions matching these schemas
- [ ] Add MemoryNode, MemoryBranch, and TranscriptEntry models
- [ ] Add JSON Schema exports for runtime validation
- [ ] Validate that all API endpoints use these types consistently
