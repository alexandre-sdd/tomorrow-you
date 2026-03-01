# Onboarding System

Onboarding is an interview-driven flow that builds enough profile context to generate a useful `currentSelf` and start exploration.

## Endpoints
- `POST /interview/start`
- `POST /interview/reply`
- `POST /interview/reply-stream`
- `GET /interview/status`
- `POST /interview/complete`

## Core Behavior
- Interview messages progressively enrich profile fields
- Completeness is tracked by `GET /interview/status`
- Completion is gated (minimum completeness threshold)
- `POST /interview/complete` finalizes `userProfile` and generates `currentSelf`

## Handoff to Exploration
After completion, pipeline flow continues with:
- `POST /pipeline/start-exploration` for root futures
- `POST /conversation/reply` to chat with a selected future self
- `POST /pipeline/branch-conversation` to generate deeper futures from transcript context

## Required Environment
- `MISTRAL_API_KEY`
- `MISTRAL_AGENT_ID_FUTURE_SELF`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_DEFAULT_VOICE_ID`

Optional onboarding agents:
- `MISTRAL_AGENT_ID_INTERVIEW`
- `MISTRAL_AGENT_ID_PROFILE_EXTRACTION`
- `MISTRAL_AGENT_ID_CURRENT_SELF_GENERATION`

## Quick Manual Run
```bash
python backend/test_onboarding_live.py --mode interactive --streaming
```

In interactive mode:
- `/status` shows extraction progress
- `/complete` finalizes onboarding and auto-starts exploration
- `/branch` creates child futures from the active conversation self