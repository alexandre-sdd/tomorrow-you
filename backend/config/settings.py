from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # Mistral
    # ------------------------------------------------------------------
    mistral_api_key: str
    mistral_model: str = "mistral-large-latest"

    # Mistral Agent IDs — one per agent created on la Plateforme
    # Create agents at https://console.mistral.ai/agents
    # Paste system prompts from prompts/<agent_name>.md into agent builder
    mistral_agent_id_future_self: str  # e.g. ag:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    mistral_agent_id_interview: str = ""  # Optional: for interview agent (can use base model)
    mistral_agent_id_profile_extraction: str = ""  # For incremental profile extraction
    mistral_agent_id_current_self_generation: str = ""  # For CurrentSelf auto-generation

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
    avatar_provider: str = "mistral"  # "mistral" | "gemini"
    gemini_api_key: str | None = None

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    storage_root: str = "./storage/sessions"
    storage_path: str = "./storage/sessions"  # Alias for backward compat
    project_root: str = "."  # Root directory of the project (for prompts/)

    model_config = {
        "env_file": str(Path(__file__).resolve().parents[2] / ".env"),
        "env_file_encoding": "utf-8",
    }


# Singleton — imported by engines and routers via get_settings()
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
