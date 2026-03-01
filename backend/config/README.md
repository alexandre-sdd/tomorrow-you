# Config Overview

This project now splits configuration into:

- `backend/config/runtime.yaml`: non-secret runtime defaults (primary file)
- `.env`: secrets and optional overrides (API keys, agent IDs, voice IDs)

## Runtime Config (`runtime.yaml`)

`runtime.yaml` is the single source of truth for non-secret knobs such as:

- chat model and sampling defaults (`mistral_chat`)
- prompt clipping limits (`prompt_composer`)
- profile summary limits (`context_resolver`)
- future generation defaults (`future_generation`)
- ancestor context limits (`future_generation_context`)
- CLI defaults (`cli`)
- app/server/storage defaults used by `Settings` (`app`, `server`, `storage`)

Load path:

- default: `backend/config/runtime.yaml` (falls back to `runtime.json` if YAML is missing)
- override: set `RUNTIME_CONFIG_PATH=/path/to/runtime.yaml` (or `.json`)

## Settings (`settings.py`)

`Settings` still loads secrets from environment variables (`.env`), while taking
non-secret defaults from `runtime.json`.

Required secrets:

- `MISTRAL_API_KEY`
- `MISTRAL_AGENT_ID_FUTURE_SELF`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_DEFAULT_VOICE_ID`

Optional secret:

- `GEMINI_API_KEY`

Optional override:

- `ELEVENLABS_VOICE_POOL_JSON`
