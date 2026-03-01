from __future__ import annotations

from typing import Iterator

from elevenlabs.client import ElevenLabs

from backend.config.runtime import get_runtime_config
from backend.config.settings import get_settings


class ElevenLabsVoiceError(RuntimeError):
    """Raised when ElevenLabs STT/TTS operations fail."""


class ElevenLabsInterviewVoiceService:
    """Thin wrapper around ElevenLabs STT/TTS for interview voice turns."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._voice_cfg = get_runtime_config().interview_voice
        self._client = ElevenLabs(api_key=self._settings.elevenlabs_api_key)

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        mime_type: str,
        language_code: str | None = None,
    ) -> str:
        if not audio_bytes:
            return ""

        extension = (mime_type.split("/", 1)[1] if "/" in mime_type else "webm").split(";", 1)[0]
        file_name = f"interview_input.{extension or 'webm'}"
        requested_language = language_code or self._voice_cfg.stt_language_code

        try:
            response = self._client.speech_to_text.convert(
                model_id=self._voice_cfg.stt_model,
                file=(file_name, audio_bytes, mime_type),
                language_code=requested_language or None,
            )
        except Exception as exc:
            raise ElevenLabsVoiceError(f"Speech-to-text failed: {exc}") from exc

        transcript = getattr(response, "text", "")
        return transcript.strip() if isinstance(transcript, str) else str(transcript or "").strip()

    def synthesize_stream(self, text: str, voice_id: str | None = None) -> Iterator[bytes]:
        chosen_voice_id = (voice_id or self._settings.elevenlabs_default_voice_id).strip()
        if not chosen_voice_id:
            raise ElevenLabsVoiceError("No ElevenLabs voice ID configured for interview TTS")
        if looks_like_placeholder_voice_id(chosen_voice_id):
            raise ElevenLabsVoiceError(
                "Invalid ElevenLabs voice ID configured for interview TTS. "
                "Set ELEVENLABS_DEFAULT_VOICE_ID in .env to a real ElevenLabs voice ID."
            )

        try:
            chunks = self._client.text_to_speech.convert(
                voice_id=chosen_voice_id,
                text=text,
                model_id=self._voice_cfg.tts_model,
                output_format=self._voice_cfg.tts_output_format,
                optimize_streaming_latency=self._voice_cfg.tts_optimize_streaming_latency,
            )
        except Exception as exc:
            raise ElevenLabsVoiceError(f"Text-to-speech failed: {exc}") from exc

        try:
            for chunk in chunks:
                if isinstance(chunk, (bytes, bytearray)) and chunk:
                    yield bytes(chunk)
        except Exception as exc:
            raise ElevenLabsVoiceError(f"Text-to-speech streaming failed: {exc}") from exc

    def tts_media_type(self) -> str:
        output_format = self._voice_cfg.tts_output_format.lower().strip()
        if output_format.startswith("mp3"):
            return "audio/mpeg"
        if output_format.startswith("wav"):
            return "audio/wav"
        if output_format.startswith("opus"):
            return "audio/ogg"
        if output_format.startswith("pcm"):
            return "audio/L16"
        return "application/octet-stream"


def looks_like_placeholder_voice_id(voice_id: str) -> bool:
    normalized = voice_id.strip().lower()
    if not normalized:
        return True
    if normalized.startswith("voice_"):
        return True
    placeholder_tokens = ("placeholder", "voice_default", "default_voice", "voice_id_here")
    return any(token in normalized for token in placeholder_tokens)
