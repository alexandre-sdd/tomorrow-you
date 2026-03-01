# Backend (FastAPI)

Backend service for onboarding, profile extraction, future-self generation, and conversation flows.

## Stack
- Python 3.11+
- FastAPI + Uvicorn
- Mistral (reasoning/generation)
- ElevenLabs (voice)

## Key Endpoints

### Onboarding
- `POST /interview/start`
- `POST /interview/reply`
- `POST /interview/reply-stream`
- `GET /interview/status`
- `POST /interview/complete`

### Pipeline
- `POST /pipeline/complete-onboarding`
- `POST /pipeline/start-exploration`
- `POST /pipeline/branch-conversation`
- `GET /pipeline/status/{session_id}`

### Conversation
- `POST /conversation/reply`
- `POST /conversation/reply-stream`

### Future Selves
- `POST /future-self/generate`

## Config
Settings are loaded from `.env` and runtime defaults from `backend/config/runtime.yaml`.

Required environment values:
- `MISTRAL_API_KEY`
- `MISTRAL_AGENT_ID_FUTURE_SELF`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_DEFAULT_VOICE_ID`

## Related Docs
- `backend/AGENT_INFRASTRUCTURE.md`
- `backend/ONBOARDING_SYSTEM.md`
- `backend/config/README.md`