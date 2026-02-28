# Config — Environment & Application Configuration

## Purpose
Centralized configuration management. API keys, service URLs, and feature flags are loaded from environment variables and exposed through a typed config object.

## Files

### `settings.py`
Pydantic Settings class that loads from `.env`:
```python
class Settings(BaseSettings):
    # Mistral
    mistral_api_key: str
    mistral_model: str = "mistral-large-latest"

    # ElevenLabs
    elevenlabs_api_key: str
    elevenlabs_default_voice_id: str

    # Avatar Generation
    avatar_provider: str = "mistral"  # "mistral" (Pixtral) or "gemini"
    gemini_api_key: str | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    # Storage
    storage_path: str = "./storage/sessions"

    class Config:
        env_file = ".env"
```

### `.env.example`
Template for required environment variables (committed to git, no real keys):
```
MISTRAL_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_DEFAULT_VOICE_ID=
AVATAR_PROVIDER=mistral
GEMINI_API_KEY=
```

## TODO
- [ ] Create Settings Pydantic model
- [ ] Create .env.example with all required variables
- [ ] Add settings dependency injection for FastAPI
- [ ] Document which API keys are required vs optional
