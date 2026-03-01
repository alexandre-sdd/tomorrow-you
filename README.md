# Tomorrow You

> *A voice-first decision exploration system. Talk to who you could become.*

Tomorrow You is an AI system that interviews you, builds a structured profile of who you are today, then generates contrasting future selves you can have real conversations with. The core bet: hearing a coherent, embodied version of a possible future — with its trade-offs, key moments, and distinct worldview — is more useful for decision-making than a list of pros and cons.

---

## What It Does

```
You talk → AI listens → Profile is built → Future selves are generated
→ You pick one → You have a voice conversation → You go deeper
```

**Five stages:**

1. **Interview** — A neutral AI interviewer extracts your life situation, values, fears, and current dilemma in 5–6 turns. It never gives advice. It reads beneath surface framing to find the real tension.

2. **Profile Reveal** — Your structured profile is surfaced: core values, fears, hidden tensions, decision style, and the specific dilemma at stake. A "current self" card is auto-generated as an emotional anchor.

3. **Future Self Selection** — 2–3 contrasting future selves are generated. Each optimizes for a meaningfully different value — not minor variations, but genuinely divergent life paths. Each has a name, worldview, trade-off, key moments from their past, a voice, and an avatar.

4. **Voice Conversation** — You talk with a selected future self. The conversation is grounded in your real profile, their backstory, and their memory branch. They know who they are.

5. **Branching** — From any conversation, you can go deeper. The system generates child futures from the context of that branch — what that version of you might become from *here*. The tree can go up to 5 levels deep, and no branch is ever lost.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                   │
│  Landing → Interview → Profile → Selection → Conversation   │
└────────────────────────────┬────────────────────────────────┘
                             │ REST (fetch)
┌────────────────────────────▼────────────────────────────────┐
│                      Backend (FastAPI)                      │
│                                                             │
│ /interview/*   /pipeline/*    /future-self/*  /conversation │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │  Interview  │  │   Pipeline   │  │  Context Resolver │   │
│  │   Agent     │  │ Orchestrator │  │  (memory walker)  │   │
│  └─────────────┘  └──────────────┘  └───────────────────┘   │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │  Profile    │  │ Future Self  │  │   Conversation    │   │
│  │ Extractor   │  │  Generator   │  │     Session       │   │
│  └─────────────┘  └──────────────┘  └───────────────────┘   │
└──────────┬──────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│                    Providers                                │
│  Mistral (LLM + Pixtral avatar)   ElevenLabs (STT + TTS)    │
└─────────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│                    Storage (file-based)                     │
│  sessions/{id}/                                             │
│  ├── session.json          (profile, all selves, state)     │
│  ├── transcript.json       (linear append-only log)         │
│  ├── avatars/              (cached AI-generated images)     │
│  └── memory/                                                │
│      ├── branches.json     (branch refs, like git refs)     │
│      └── nodes/            (memory tree nodes)              │
└─────────────────────────────────────────────────────────────┘
```

---

## Memory System: Git-like Branching

The memory system is one of the core design innovations. It separates two orthogonal concerns:

**Transcript** (linear, append-only): The record of what happened. Interview turns, conversation turns, system events, branch switches. Never deletes, never branches.

**Memory Tree** (branching): The record of what we know about each path. Each node holds facts and notes. Nodes branch at decision points (when the user picks a self). Resolution works like `git log`: walk from root to HEAD, collect all facts on the path.

```
Current Self (root)
├── Singapore Self (depth 1)        ← branch: singapore_branch_1
│   ├── Found Community (depth 2)   ← branch: found_community_branch
│   └── Burned Out (depth 2)        ← branch: burned_out_branch
└── NYC Self (depth 1)              ← branch: nyc_branch_1
    ├── Started Business (depth 2)
    └── Family Expanded (depth 2)
```

All selves are preserved in `futureSelvesFull` (no data loss when switching branches). `explorationPaths` tracks the parent→children mapping. Switching branches is non-destructive — you can return to any prior path.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, Tailwind CSS, TypeScript |
| State | React hooks (client-side, screen-level) |
| Backend | Python FastAPI (fully async) |
| LLM | Mistral (agents API, strict JSON schema enforcement) |
| Voice | ElevenLabs — both STT and TTS |
| Avatars | Mistral Pixtral (primary), Gemini (fallback) |
| Storage | File-based JSON (session-scoped, git-like structure) |

---

## Key Design Decisions

**Python backend, not Node.** The Mistral and ElevenLabs Python SDKs are significantly more complete than their JS equivalents. Async FastAPI provides the same non-blocking performance.

**Prompts in files, not code.** All Mistral system prompts live in `prompts/*.md`. They are editable reference files — change a prompt, restart, iterate. No grep-and-replace through engine code.

**Mistral JSON schema enforcement everywhere.** Every LLM call uses `response_format` with a strict JSON schema. No freeform output, no parsing heuristics. This makes outputs reliable enough to use directly as data.

**The "current self" step.** Before showing future selves, the system generates a "current self" card from the completed profile. This is an emotional anchor — it names who you are now before asking who you could become. Without it, the future selves feel abstract.

**Voice assignment by mood.** Mistral generates each future self with a `mood` (elevated, warm, sharp, grounded, ethereal, intense, calm). The backend maps mood → ElevenLabs voice ID from a configurable pool. Uniqueness is guaranteed per batch — no two selves in a generation share a voice.

**Avatar URLs always null from LLM.** The LLM generates an `avatar_prompt` — a cinematic, 3–5 sentence description. Avatar generation runs separately, images are cached to `storage/sessions/{id}/avatars/`. This decouples the expensive image generation from the persona generation.

**Stateless conversation per request.** The frontend owns conversation history and sends it on every turn. The backend loads context from the memory tree, assembles the full prompt, calls Mistral, and returns the reply. No shared in-memory state.

---

## Project Structure

```
tomorrow-you/
├── backend/
│   ├── app.py                          # FastAPI factory + middleware
│   ├── main.py                         # Uvicorn entry point
│   ├── config/
│   │   ├── settings.py                 # Pydantic Settings (env vars)
│   │   └── runtime.json                # Default runtime config
│   ├── engines/
│   │   ├── future_self_generator.py    # Core persona generation + voice assignment
│   │   ├── profile_extractor.py        # Incremental profile extraction
│   │   ├── current_self_auto_generator.py
│   │   ├── conversation_session.py     # Stateless conversation handler
│   │   ├── context_resolver.py         # Memory tree walker (read-only)
│   │   ├── prompt_composer.py          # Context-aware prompt assembly
│   │   ├── pipeline_orchestrator.py    # Multi-step workflow coordination
│   │   ├── conversation_memory.py      # Transcript persistence + insight extraction
│   │   ├── future_gen_context.py       # Ancestor context resolution for branching
│   │   └── mistral_client.py           # Mistral SDK wrapper
│   ├── models/
│   │   └── schemas.py                  # All Pydantic models (source of truth)
│   ├── routers/
│   │   ├── onboarding.py               # /interview/* endpoints
│   │   ├── future_self.py              # /future-self/* endpoints
│   │   ├── conversation.py             # /conversation/* endpoints
│   │   └── pipeline.py                 # /pipeline/* endpoints
│   └── test_onboarding_live.py         # Interactive CLI for full flow testing
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                    # Main app shell + all state
│   │   └── layout.tsx                  # Root HTML layout
│   ├── screens/
│   │   ├── LandingScreen.tsx
│   │   ├── InterviewScreen.tsx
│   │   ├── ProfileRevealScreen.tsx
│   │   ├── SelfSelectionScreen.tsx
│   │   └── ConversationScreen.tsx
│   ├── components/
│   │   ├── AppShell.tsx
│   │   ├── ChatPanel.tsx
│   │   ├── SelfCardPanel.tsx
│   │   ├── MessageBubble.tsx
│   │   └── ...
│   └── lib/
│       ├── types.ts                    # TypeScript types (mirrors backend schemas)
│       ├── api.ts                      # Backend API client
│       ├── mocks.ts                    # Mock session (NYC/Singapore example)
│       └── timeHorizon.ts              # Depth → time horizon label mapping
│
├── prompts/
│   ├── interview_agent.md              # Interview Agent system prompt
│   ├── profile_extraction.md           # Profile Extractor system prompt
│   └── future_self_generation.md       # Future Self Generator system prompt
│
├── shared/                             # Data contracts (source of truth)
├── storage/                            # Session data (gitignored)
│   └── sessions/{session_id}/
│       ├── session.json
│       ├── transcript.json
│       ├── avatars/
│       └── memory/
└── .env.example
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Mistral account with at least one agent configured
- An ElevenLabs account with voice IDs selected

### 1. Clone & configure

```bash
git clone <repo>
cd tomorrow-you
cp .env.example .env
```

### 2. Configure environment

Edit `.env`:

```bash
# Required: Mistral
MISTRAL_API_KEY=your_key_here
MISTRAL_MODEL=mistral-large-latest

# Create an agent at https://console.mistral.ai/agents
# Paste the content of prompts/future_self_generation.md as the system prompt
MISTRAL_AGENT_ID_FUTURE_SELF=ag:xxxxxxxx

# Required: ElevenLabs
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_DEFAULT_VOICE_ID=your_default_voice_id

# Map each mood to an ElevenLabs voice ID (all 7 required)
# Find voice IDs at https://elevenlabs.io/app/voice-library
ELEVENLABS_VOICE_POOL_JSON={"elevated":"id1","warm":"id2","sharp":"id3","grounded":"id4","calm":"id5","intense":"id6","ethereal":"id7"}

# Optional: Avatar generation (Mistral Pixtral is default)
AVATAR_PROVIDER=mistral
```

**Mistral agent setup:** Go to [console.mistral.ai/agents](https://console.mistral.ai/agents), create a new agent, paste the contents of `prompts/future_self_generation.md` as the system prompt, copy the agent ID (format: `ag:xxxxxxxx`), paste it into `.env`.

You can optionally create additional agents for the interview and profile extraction using `prompts/interview_agent.md` and `prompts/profile_extraction.md`.

### 3. Start the backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## API Reference

### Onboarding

| Method | Path | Description |
|--------|------|-------------|
| POST | `/interview/start` | Initialize session, get first question |
| POST | `/interview/reply` | Send user message, get next question + extraction update |
| GET | `/interview/status` | Profile completeness score + which dimensions are filled |
| POST | `/interview/complete` | Finalize onboarding, auto-generate current self |

### Pipeline (orchestrated workflows)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/pipeline/complete-onboarding` | Interview completion + current self generation in one call |
| POST | `/pipeline/start-exploration` | Generate root future selves |
| POST | `/pipeline/branch-conversation` | Generate child futures from conversation context |
| GET | `/pipeline/status/{session_id}` | Phase, depth, counts, conversation-capable branches |

### Future Selves

| Method | Path | Description |
|--------|------|-------------|
| POST | `/future-self/generate` | Generate selves (root if `parentSelfId=null`, branching if set) |

### Conversation

| Method | Path | Description |
|--------|------|-------------|
| POST | `/conversation/reply` | Send message to a future self, receive reply |

---

## Testing

### Interactive CLI (recommended for development)

```bash
python backend/test_onboarding_live.py --mode interactive --streaming
```

This runs the full pipeline interactively. Commands:

- `/complete` — finalize onboarding and generate future selves
- `/use <id>` — select a future self to converse with
- `/branch` — generate child futures from the current branch

### End-to-end test

```bash
python backend/test_full_pipeline_e2e.py
```

---

## How Persona Generation Works

The `FutureSelfGenerator` engine:

1. **Builds a `GenerationContext`** — user profile, current self, parent self (if branching), ancestor summary from walking the memory tree, conversation excerpts, sibling names to avoid duplication, depth level, and time horizon label.

2. **Calls the Mistral agent** with strict JSON schema enforcement (`response_format`). The schema maps directly to `RawFutureSelvesOutput`. No freeform output is ever parsed.

3. **Assigns voice IDs** by mapping the generated `mood` field to an ElevenLabs voice ID from the pool. Uniqueness is guaranteed per batch — if two selves share a mood, one gets the next available voice.

4. **Generates content-hashed IDs** — `sha256(name|parent_id|timestamp[:10])[:10]` — so IDs are deterministic but collision-free.

5. **Returns `SelfCard` objects** with all tree fields set (`parent_self_id`, `depth_level`, `children_ids`), avatar URL always null (generated separately).

### What makes the prompts work

The interview agent is explicitly instructed to never give advice, never re-ask what's already known, and to read emotionally charged moments rather than surface content. It has a 5–6 turn budget and a specific progression:

- Turn 1: Open + orient
- Turns 2–4: Follow the thread, combine dimensions naturally
- Turn 5–6: Name the real tension, ask for confirmation

The future self generator is given specific rules that prevent generic outputs: trade-offs must be "emotionally costly, not minor inconveniences," names must be natural-language labels not personality archetypes, and visual styles must be distinct (no color reuse within a batch).

---

## Prompts

All Mistral system prompts live in `prompts/`. They are the primary interface for tuning generation quality. Change a prompt, restart the backend, and the change is live — no code changes needed.

| File | Purpose |
|------|---------|
| `prompts/interview_agent.md` | Neutral intake interviewer (extraction-focused, non-advisory) |
| `prompts/profile_extraction.md` | Incremental profile builder with confidence scoring and interview signal generation |
| `prompts/future_self_generation.md` | Future persona architect with strict contrast and trade-off rules |

---

## Data Model

The canonical data contracts are defined in `backend/models/schemas.py` (Pydantic) and mirrored in `frontend/lib/types.ts` (TypeScript).

Key types:

**`SelfCard`** — a single persona (current or future):
- `id`, `type` (current | future), `name`
- `optimization_goal`, `tone_of_voice`, `worldview`, `core_belief`
- `trade_off` — what this path costs (must be emotionally significant)
- `key_moments[]` — 2–3 specific past events, grounding for conversation
- `avatar_prompt`, `avatar_url` (null until generated)
- `visual_style` — primary color, accent color, mood, glow intensity
- `voice_id` — ElevenLabs voice assigned by mood
- Tree fields: `parent_self_id`, `depth_level`, `children_ids`

**`UserProfile`** — extracted from the interview:
- `core_values[]`, `fears[]`, `hidden_tensions[]`
- `decision_style`, `self_narrative`, `current_dilemma`
- Nested sections: `CareerProfile`, `FinancialProfile`, `PersonalProfile`, `HealthProfile`, `LifeSituationProfile`

---

## Implementation Status

**Done:**
- Full backend pipeline: interview → extraction → current self → future generation → conversation → branching
- Memory tree architecture with full branch navigation
- Frontend: all 5 screens wired to backend API
- Prompt system (interview, extraction, future self generation)
- Voice assignment pipeline (mood → ElevenLabs voice pool)
- Mock session data for frontend development without API calls

**In progress / not started:**
- ElevenLabs STT/TTS integration (voice pipeline)
- Avatar generation (Pixtral/Gemini)
- SessionStore persistence layer (currently file-based, no cleanup)
- WebSocket support for real-time voice streaming
- Debrief / summary screen
