"""
Avatar Generator Engine

Generates profile avatar images for SelfCards using Mistral's image generation
agent (beta). All avatars share the same illustrated art style — think Xbox
gamerpic / stylised 3-D character portrait — so every branch in the tree looks
like it belongs to the same visual universe.

Images are saved to storage/sessions/{session_id}/avatars/{self_id}.png and
served via the /avatars static mount in main.py.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import re
from pathlib import Path
from typing import Any

from mistralai import Mistral
from mistralai.models import ToolFileChunk

from backend.config.settings import get_settings
from backend.models.schemas import SelfCard


# ---------------------------------------------------------------------------
# Shared art-direction for ALL avatars
# ---------------------------------------------------------------------------
# Every future self gets the same visual "universe" — an Xbox-style stylised
# 3-D illustrated character portrait — so branching selves feel like
# variations in the same world rather than random stock photos.
_STYLE_DIRECTIVE = (
    "Art style: stylised 3-D illustrated character portrait, Xbox gamerpic aesthetic. "
    "Smooth cel-shading, vibrant but harmonious colours, expressive face, "
    "simple clean background (soft gradient or plain colour that matches the character's mood). "
    "NOT photorealistic. Consistent illustrated look across the full series of avatars. "
    "Square or circular crop, face and upper shoulders fill the frame. No text, no borders."
)

_AGENT_INSTRUCTIONS = (
    "You are an avatar illustrator. When asked to generate a character portrait, "
    "always use the image generation tool. "
    "All portraits you create must share the same visual style: "
    + _STYLE_DIRECTIVE
)

_MAX_REFERENCE_PHOTO_B64_CHARS = 2_500_000


class AvatarGenerator:
    """Generates avatar images for SelfCards using Mistral image generation."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = Mistral(api_key=self.settings.mistral_api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(self, self_card: SelfCard, session_id: str) -> str | None:
        """
        Generate a profile portrait for a single SelfCard.

        Returns the served URL of the saved PNG, or None if generation fails.
        """
        try:
            agent_id = await self._get_or_create_agent()
            inputs = self._build_inputs(self_card, session_id)

            response = await asyncio.to_thread(
                self.client.beta.conversations.start,
                agent_id=agent_id,
                inputs=inputs,
            )

            image_bytes = await self._download_generated_image(response)
            if image_bytes is None:
                print(
                    f"[AvatarGenerator] No generated tool file found for '{self_card.name}'"
                )
                return None

            return self._save_image_bytes(image_bytes, self_card.id, session_id)

        except Exception as exc:
            print(f"[AvatarGenerator] Generation failed for '{self_card.name}': {exc}")
            return None

    async def generate_all(
        self,
        cards: list[SelfCard],
        session_id: str,
    ) -> list[SelfCard]:
        """
        Generate avatars for all cards in parallel.

        Returns a new list of SelfCards with avatar_url populated where
        generation succeeded; cards that failed keep avatar_url=None.
        """
        urls = await asyncio.gather(
            *[self.generate(card, session_id) for card in cards],
            return_exceptions=True,
        )

        result: list[SelfCard] = []
        for card, url in zip(cards, urls):
            if isinstance(url, str):
                result.append(card.model_copy(update={"avatar_url": url}))
            else:
                result.append(card)
        return result

    # ------------------------------------------------------------------
    # Mistral agent management
    # ------------------------------------------------------------------

    async def _get_or_create_agent(self) -> str:
        """Create a fresh image generation agent and return its ID."""
        agent = await asyncio.to_thread(
            self.client.beta.agents.create,
            model=self.settings.mistral_image_model,
            name="Avatar Generation Agent",
            description="Generates stylised Xbox-style portrait avatars for future self personas.",
            instructions=_AGENT_INSTRUCTIONS,
            tools=[{"type": "image_generation"}],
            completion_args={"temperature": 0.3, "top_p": 0.95},
        )
        print(f"[AvatarGenerator] Created agent: {agent.id}")
        return agent.id

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_inputs(
        self,
        self_card: SelfCard,
        session_id: str,
    ) -> list[dict[str, Any]]:
        prompt = self._build_prompt(self_card)
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        photo = self._load_user_photo(session_id)

        if photo:
            photo_b64, mime_type = photo
            if len(photo_b64) <= _MAX_REFERENCE_PHOTO_B64_CHARS:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{photo_b64}",
                        },
                    }
                )
            else:
                print(
                    "[AvatarGenerator] Reference photo too large for inline input; "
                    "skipping likeness transfer."
                )

        return [{"role": "user", "content": content}]

    def _build_prompt(
        self,
        self_card: SelfCard,
    ) -> str:
        # Strip the photorealism cues from the LLM-generated prompt and keep
        # only the character description — the style is enforced by the agent.
        character_description = self._strip_photorealism(self_card.avatar_prompt)
        primary_color = self_card.visual_style.primary_color
        accent_color = self_card.visual_style.accent_color

        return (
            "Generate exactly one avatar portrait.\n"
            f"Persona name: {self_card.name}\n"
            f"Optimization goal: {self_card.optimization_goal}\n"
            f"Tone: {self_card.tone_of_voice}\n"
            f"Character description: {character_description}\n"
            f"Palette preference: primary {primary_color}, accent {accent_color}.\n"
            f"{_STYLE_DIRECTIVE}\n"
            "If an image is provided, preserve facial identity, skin tone, and hairstyle.\n"
            "Quality constraints: single subject only, centered composition, anatomically correct face, "
            "sharp eyes, clean edges, no text, no logos, no watermark, no extra limbs."
        )

    @staticmethod
    def _strip_photorealism(prompt: str) -> str:
        """Remove photography/realism style cues that would fight the avatar style."""
        drop_phrases = [
            "cinematic", "photorealistic", "realistic", "editorial photography",
            "premium", "stock photo", "portrait photography", "film grain",
            "depth of field", "bokeh", "35mm", "lens",
        ]
        result = prompt
        for phrase in drop_phrases:
            result = re.sub(re.escape(phrase), "", result, flags=re.IGNORECASE)
        # Collapse multiple spaces
        return re.sub(r"\s{2,}", " ", result).strip()

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    async def _download_generated_image(self, conversation_response: Any) -> bytes | None:
        file_id = self._extract_tool_file_id(conversation_response)
        if not file_id:
            print(
                "[AvatarGenerator] Could not find tool_file in conversation response:\n"
                + self._safe_dump(conversation_response)
            )
            return None

        file_response = await asyncio.to_thread(self.client.files.download, file_id=file_id)
        return file_response.read()

    def _extract_tool_file_id(self, conversation_response: Any) -> str | None:
        outputs = getattr(conversation_response, "outputs", None) or []
        for output in outputs:
            content = getattr(output, "content", None) or []
            for chunk in content:
                # Strongly-typed SDK chunk
                if isinstance(chunk, ToolFileChunk):
                    return chunk.file_id

                # Generic object form
                chunk_type = getattr(chunk, "type", None)
                if chunk_type == "tool_file":
                    file_id = getattr(chunk, "file_id", None)
                    if file_id:
                        return file_id

                # Dict form fallback
                if isinstance(chunk, dict) and chunk.get("type") == "tool_file":
                    file_id = chunk.get("file_id")
                    if file_id:
                        return str(file_id)

        return None

    @staticmethod
    def _to_str(obj: Any) -> str:
        if isinstance(obj, str):
            return obj
        try:
            return json.dumps(obj if isinstance(obj, dict) else obj.__dict__)
        except Exception:
            return str(obj)

    @staticmethod
    def _safe_dump(obj: Any) -> str:
        try:
            return json.dumps(obj, default=lambda o: repr(o), indent=2)[:2000]
        except Exception:
            return repr(obj)[:2000]

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    def _load_user_photo(self, session_id: str) -> tuple[str, str] | None:
        session_dir = Path(self.settings.storage_root) / session_id
        b64_path = session_dir / "user_photo.b64"
        if not b64_path.exists():
            return None

        photo_b64 = b64_path.read_text(encoding="utf-8").strip()
        if not photo_b64:
            return None

        mime_path = session_dir / "user_photo.mime"
        mime_type = mime_path.read_text(encoding="utf-8").strip() if mime_path.exists() else ""
        if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            mime_type = self._guess_image_mime(photo_b64)

        return photo_b64, mime_type

    @staticmethod
    def _guess_image_mime(photo_b64: str) -> str:
        try:
            raw = base64.b64decode(photo_b64, validate=True)
        except (binascii.Error, ValueError):
            return "image/jpeg"

        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if raw.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"

    def _save_image_bytes(self, image_bytes: bytes, self_id: str, session_id: str) -> str:
        avatar_dir = Path(self.settings.storage_root) / session_id / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)
        avatar_path = avatar_dir / f"{self_id}.png"
        avatar_path.write_bytes(image_bytes)
        url = f"/avatars/{session_id}/avatars/{self_id}.png"
        print(f"[AvatarGenerator] Saved avatar → {url}")
        return url
