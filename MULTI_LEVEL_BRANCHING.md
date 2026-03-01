# Multi-Level Branching

## Purpose
Enable tree-based exploration of futures without losing prior branches.

## Core Idea
- Root generation creates level-1 alternatives.
- Branch generation creates level-2+ alternatives from a selected parent self.
- All selves remain in session state for later navigation.

## Tree Model
```text
Current Self (root)
├─ Future A (depth 1)
│  ├─ Future A1 (depth 2)
│  └─ Future A2 (depth 2)
└─ Future B (depth 1)
   ├─ Future B1 (depth 2)
   └─ Future B2 (depth 2)
```

## Session Fields
- `futureSelvesFull`: dictionary of all future selves by ID
- `explorationPaths`: mapping of parent ID (`root` or self ID) to child IDs
- `futureSelfOptions`: root-level compatibility list

## SelfCard Branch Fields
- `parent_self_id`: parent self ID (`null` for root futures)
- `depth_level`: depth in tree
- `children_ids`: generated children for a self

## API Flow
### 1) Generate Root Futures
`POST /future-self/generate` with `parentSelfId=null`

### 2) Generate Child Futures
`POST /future-self/generate` with `parentSelfId=<selected_self_id>`

### 3) Pipeline Branching
`POST /pipeline/branch-conversation` uses conversation context and parent self

### 4) Inspect State
`GET /pipeline/status/{session_id}` for phase, counts, depth, and conversation-capable branches

## Branching Preconditions
- Onboarding complete (`currentSelf` exists)
- Parent self exists
- Conversation context should exist on that branch for best results

## Why It Works
- No data loss: all branches are preserved
- Reversible exploration: users can move between branches
- Context continuity: ancestor + transcript context informs deeper generation

## Practical Test Path
1. Complete onboarding
2. Start exploration
3. Converse with one root self
4. Branch from that conversation
5. Verify depth/count via pipeline status

## Quick Command
```bash
python backend/test_onboarding_live.py --mode interactive --streaming
```