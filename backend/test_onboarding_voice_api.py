from __future__ import annotations

import base64
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

# Ensure required settings exist for app import in test contexts.
os.environ.setdefault("MISTRAL_API_KEY", "test_mistral_key")
os.environ.setdefault("MISTRAL_AGENT_ID_FUTURE_SELF", "ag:test_future")
os.environ.setdefault("ELEVENLABS_API_KEY", "test_elevenlabs_key")
os.environ.setdefault("ELEVENLABS_DEFAULT_VOICE_ID", "voice_test_default")

from backend.app import app


def _runtime_with_limits(max_bytes: int) -> SimpleNamespace:
    interview_voice = SimpleNamespace(
        enabled=True,
        stt_model="scribe_v2",
        stt_language_code="en",
        stt_max_audio_bytes=max_bytes,
        tts_model="eleven_flash_v2_5",
        tts_output_format="mp3_44100_128",
        tts_optimize_streaming_latency=0,
    )
    return SimpleNamespace(interview_voice=interview_voice)


class OnboardingVoiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_transcribe_rejects_invalid_base64(self) -> None:
        with patch(
            "backend.routers.onboarding.get_runtime_config",
            return_value=_runtime_with_limits(max_bytes=1024),
        ):
            response = self.client.post(
                "/interview/transcribe",
                json={
                    "sessionId": "session_voice_invalid",
                    "audioBase64": "!!!not_base64!!!",
                    "mimeType": "audio/webm",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid base64", response.text)

    def test_transcribe_enforces_max_size(self) -> None:
        payload = base64.b64encode(b"12345").decode("utf-8")

        with patch(
            "backend.routers.onboarding.get_runtime_config",
            return_value=_runtime_with_limits(max_bytes=4),
        ):
            response = self.client.post(
                "/interview/transcribe",
                json={
                    "sessionId": "session_voice_oversize",
                    "audioBase64": payload,
                    "mimeType": "audio/webm",
                },
            )

        self.assertEqual(response.status_code, 413)
        self.assertIn("Audio payload too large", response.text)

    def test_transcribe_success_with_mocked_elevenlabs(self) -> None:
        payload = base64.b64encode(b"hello-audio").decode("utf-8")

        with patch(
            "backend.routers.onboarding.get_runtime_config",
            return_value=_runtime_with_limits(max_bytes=1024),
        ), patch(
            "backend.engines.elevenlabs_voice.ElevenLabsInterviewVoiceService.transcribe_bytes",
            return_value="hello from stt",
        ):
            response = self.client.post(
                "/interview/transcribe",
                json={
                    "sessionId": "session_voice_ok",
                    "audioBase64": payload,
                    "mimeType": "audio/webm",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["sessionId"], "session_voice_ok")
        self.assertEqual(body["transcriptText"], "hello from stt")

    def test_tts_rejects_blank_text(self) -> None:
        with patch(
            "backend.routers.onboarding.get_runtime_config",
            return_value=_runtime_with_limits(max_bytes=1024),
        ):
            response = self.client.post(
                "/interview/tts",
                json={
                    "sessionId": "session_voice_tts_blank",
                    "text": "   ",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("text must not be empty", response.text)

    def test_tts_streams_audio_bytes(self) -> None:
        with patch(
            "backend.routers.onboarding.get_runtime_config",
            return_value=_runtime_with_limits(max_bytes=1024),
        ), patch(
            "backend.engines.elevenlabs_voice.ElevenLabsInterviewVoiceService.synthesize_stream",
            return_value=iter([b"chunk1", b"chunk2"]),
        ), patch(
            "backend.engines.elevenlabs_voice.ElevenLabsInterviewVoiceService.tts_media_type",
            return_value="audio/mpeg",
        ):
            response = self.client.post(
                "/interview/tts",
                json={
                    "sessionId": "session_voice_tts_ok",
                    "text": "hello in audio",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type"), "audio/mpeg")
        self.assertEqual(response.content, b"chunk1chunk2")


if __name__ == "__main__":
    unittest.main()
