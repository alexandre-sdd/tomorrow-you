from __future__ import annotations

import json
import os
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

# Ensure required settings exist for app import in test contexts.
os.environ.setdefault("MISTRAL_API_KEY", "test_mistral_key")
os.environ.setdefault("MISTRAL_AGENT_ID_FUTURE_SELF", "ag:test_future")
os.environ.setdefault("ELEVENLABS_API_KEY", "test_elevenlabs_key")
os.environ.setdefault("ELEVENLABS_DEFAULT_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

from backend.app import app
from backend.config.settings import get_settings


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


class ConversationVoiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        storage_root = get_settings().storage_root
        self.settings_stub = SimpleNamespace(
            storage_path=storage_root,
            elevenlabs_default_voice_id="C0nVersaTionDefaUlt01",
            elevenlabs_chat_default_male_voice_id="C0nVersaTionMale0001",
            elevenlabs_chat_default_female_voice_id="C0nVersaTionFemal001",
        )
        app.dependency_overrides[get_settings] = lambda: self.settings_stub

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _session_dir(self, session_id: str) -> Path:
        return Path(self.settings_stub.storage_path) / session_id

    def _session_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "session.json"

    def _write_session(self, session_id: str) -> None:
        session_dir = self._session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": session_id,
            "status": "conversation",
            "transcript": [],
            "userProfile": {"id": "user_1"},
            "currentSelf": None,
            "createdAt": 0,
            "updatedAt": 0,
        }
        self._session_path(session_id).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _cleanup_session(self, session_id: str) -> None:
        shutil.rmtree(self._session_dir(session_id), ignore_errors=True)

    def test_conversation_tts_locks_gender_voice_across_branches(self) -> None:
        session_id = "session_convo_voice_lock"
        self._cleanup_session(session_id)
        self._write_session(session_id)

        selected_voice_ids: list[str | None] = []
        contexts = [
            (
                "branch_a",
                SimpleNamespace(
                    user_profile={"self_narrative": "I am a woman building my next chapter."},
                    self_card={"id": "self_a", "voice_id": "branch_voice_a"},
                ),
            ),
            (
                "branch_b",
                SimpleNamespace(
                    user_profile={"self_narrative": "I am a man rethinking this decision."},
                    self_card={"id": "self_b", "voice_id": "branch_voice_b"},
                ),
            ),
        ]

        def _fake_resolve(*args, **kwargs):
            return contexts.pop(0)

        def _capture_voice(*args, **kwargs):
            selected_voice_ids.append(kwargs.get("voice_id"))
            return iter([b"chunk"])

        with patch(
            "backend.routers.conversation.get_runtime_config",
            return_value=_runtime_with_limits(max_bytes=1024),
        ), patch(
            "backend.routers.conversation._resolve_branch_context",
            side_effect=_fake_resolve,
        ), patch(
            "backend.engines.elevenlabs_voice.ElevenLabsInterviewVoiceService.synthesize_stream",
            side_effect=_capture_voice,
        ), patch(
            "backend.engines.elevenlabs_voice.ElevenLabsInterviewVoiceService.tts_media_type",
            return_value="audio/mpeg",
        ):
            first = self.client.post(
                "/conversation/tts",
                json={
                    "sessionId": session_id,
                    "selfId": "self_a",
                    "text": "first reply",
                },
            )
            second = self.client.post(
                "/conversation/tts",
                json={
                    "sessionId": session_id,
                    "selfId": "self_b",
                    "text": "second reply",
                },
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            selected_voice_ids,
            ["C0nVersaTionFemal001", "C0nVersaTionFemal001"],
        )
        self.assertEqual(first.headers.get("x-conversation-voice-id"), "C0nVersaTionFemal001")
        self.assertEqual(second.headers.get("x-conversation-voice-id"), "C0nVersaTionFemal001")

        saved = json.loads(self._session_path(session_id).read_text(encoding="utf-8"))
        self.assertEqual(saved.get("voiceConfig", {}).get("conversationVoiceId"), "C0nVersaTionFemal001")
        self.assertEqual(saved.get("voiceConfig", {}).get("conversationVoiceGender"), "female")
        self._cleanup_session(session_id)


if __name__ == "__main__":
    unittest.main()
