# Tomorrow You

Tomorrow You is an AI experience for high-stakes life decisions.  
You speak about your current crossroads, and the system generates multiple plausible future versions of you that you can talk to directly.

## What Judges Should Know

- This is a working end-to-end MVP.
- The product is centered on emotionally grounded decision support, not generic chat.
- The core value is branching futures: you can explore different life paths and continue branching from each one.

## Core Experience

1. **Interview (voice or text)**  
   A guided onboarding interview captures your context, fears, values, and dilemma.
2. **Future selves generation**  
   The system creates contrasting future personas from your profile.
3. **Conversation + branching**  
   You chat with one future self, then branch again to see how that path evolves.

## Tech Used

- **Mistral**: interview intelligence, profile extraction, future-self generation, and conversation reasoning.
- **ElevenLabs**: speech-to-text and text-to-speech for voice interaction during onboarding.
- **FastAPI + Next.js**: backend orchestration and frontend product experience.

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

## Judge Quickstart

### 1. Configure environment

Copy env template and add keys:

```bash
cp .env.example .env
```

Required keys:

- `MISTRAL_API_KEY`
- `MISTRAL_AGENT_ID_FUTURE_SELF`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_DEFAULT_VOICE_ID` (must be a real ElevenLabs voice ID)

### 2. Run app

From project root:

```bash
./start.sh
```

Then open:

- Frontend: `http://localhost:3000`
- Backend docs: `http://localhost:8000/docs`

## 2-Minute Demo Flow

1. Start interview and answer a few prompts (voice or text).
2. Complete onboarding (after profile completeness threshold).
3. Select a generated future self.
4. Chat, then trigger a branch from that conversation.
5. Observe new child futures generated from that exact path context.

## Why This Is Different

- Not a single “assistant persona”: it builds multiple coherent identities from one user.
- Not stateless advice: each branch has memory and continuity.
- Not text-only: voice makes the interview and reflection feel natural.

## Current Scope (Hackathon)

- Fully functional local MVP.
- File-based session storage (no cloud persistence layer yet).
- Focused on decision exploration quality over production hardening.

## Repo Pointers

- Product architecture overview: [architecture.md](architecture.md)
- Backend infra notes: [backend/AGENT_INFRASTRUCTURE.md](backend/AGENT_INFRASTRUCTURE.md)
- Engine internals: [backend/engines/README.md](backend/engines/README.md)
