from __future__ import annotations

import json

from pydantic import Field
from pydantic_settings import BaseSettings

from .runtime import get_runtime_config

_runtime = get_runtime_config()


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # Mistral
    # ------------------------------------------------------------------
    mistral_api_key: str
    mistral_model: str = _runtime.app.mistral_model

    # Mistral Agent IDs — one per agent created on la Plateforme
    mistral_agent_id_future_self: str  # e.g. ag:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

    # ------------------------------------------------------------------
    # ElevenLabs
    # ------------------------------------------------------------------
    elevenlabs_api_key: str
    # Neutral fallback voice used by the interview agent and as last-resort
    elevenlabs_default_voice_id: str

    # Voice pool — JSON string in .env mapping mood → ElevenLabs voice ID.
    # Example .env value:
    # ELEVENLABS_VOICE_POOL_JSON={"elevated":"21m00Tcm4TlvDq8ikWAM","warm":"AZnzlk1XvdvUeBnXmlld","sharp":"EXAVITQu4vr4xnSDxMaL","grounded":"ErXwobaYiN019PkySvjV","calm":"MF3mGyEYCl7XYWbV9V6O","intense":"VR6AewLTigWG4xSOukaG","ethereal":"pNInz6obpgDQGcFmaJgB"}
    elevenlabs_voice_pool_json: str = Field(default="{}")

    @property
    def elevenlabs_voice_pool(self) -> dict[str, str]:
        """Returns mood → voice_id mapping parsed from the JSON env var."""
        return json.loads(self.elevenlabs_voice_pool_json)

    # ------------------------------------------------------------------
    # Avatar generation
    # ------------------------------------------------------------------
    avatar_provider: str = _runtime.app.avatar_provider  # "mistral" | "gemini"
    gemini_api_key: str | None = None

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------
    host: str = _runtime.server.host
    port: int = _runtime.server.port
    cors_origins: list[str] = Field(default_factory=lambda: list(_runtime.server.cors_origins))

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    storage_path: str = _runtime.storage.path

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Singleton — imported by engines and routers via get_settings()
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
