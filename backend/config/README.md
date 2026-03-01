# Backend Config

Configuration is split into:
- `runtime.yaml` for non-secret runtime defaults
- `.env` for secrets and agent/voice IDs

## Runtime Config
`backend/config/runtime.yaml` contains defaults for:
- models and generation behavior
- context/memory limits
- app/server/storage defaults
- interview voice defaults (`interview_voice.*`) for ElevenLabs STT/TTS

Override file path with:
- `RUNTIME_CONFIG_PATH=/path/to/runtime.yaml`

## Environment Variables
Required:
- `MISTRAL_API_KEY`
- `MISTRAL_AGENT_ID_FUTURE_SELF`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_DEFAULT_VOICE_ID`

Optional:
- `MISTRAL_AGENT_ID_INTERVIEW`
- `MISTRAL_AGENT_ID_PROFILE_EXTRACTION`
- `MISTRAL_AGENT_ID_CURRENT_SELF_GENERATION`
- `ELEVENLABS_VOICE_POOL_JSON`
- `GEMINI_API_KEY`

## Loading Behavior
`backend/config/settings.py` loads `.env` values and merges runtime defaults from `runtime.yaml`.
