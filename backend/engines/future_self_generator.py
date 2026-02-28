from __future__ import annotations

import uuid

from mistralai import Mistral

from backend.config.settings import get_settings
from backend.models.schemas import (
    RawFutureSelvesOutput,
    RawSelfCard,
    SelfCard,
    UserProfile,
    VisualStyle,
)

# ---------------------------------------------------------------------------
# JSON schema enforced via Mistral's response_format
# ---------------------------------------------------------------------------

FUTURE_SELF_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "future_selves",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "future_selves": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "required": [
                            "type",
                            "name",
                            "optimization_goal",
                            "tone_of_voice",
                            "worldview",
                            "core_belief",
                            "trade_off",
                            "avatar_prompt",
                            "avatar_url",
                            "visual_style",
                            "voice_id",
                        ],
                        "properties": {
                            "type": {"type": "string", "enum": ["future"]},
                            "name": {"type": "string"},
                            "optimization_goal": {"type": "string"},
                            "tone_of_voice": {"type": "string"},
                            "worldview": {"type": "string"},
                            "core_belief": {"type": "string"},
                            "trade_off": {"type": "string"},
                            "avatar_prompt": {"type": "string"},
                            "avatar_url": {"type": "null"},
                            "visual_style": {
                                "type": "object",
                                "required": [
                                    "primary_color",
                                    "accent_color",
                                    "mood",
                                    "glow_intensity",
                                ],
                                "properties": {
                                    "primary_color": {
                                        "type": "string",
                                        "pattern": "^#[0-9A-Fa-f]{6}$",
                                    },
                                    "accent_color": {
                                        "type": "string",
                                        "pattern": "^#[0-9A-Fa-f]{6}$",
                                    },
                                    "mood": {
                                        "type": "string",
                                        "enum": [
                                            "elevated",
                                            "warm",
                                            "sharp",
                                            "grounded",
                                            "ethereal",
                                            "intense",
                                            "calm",
                                        ],
                                    },
                                    "glow_intensity": {
                                        "type": "number",
                                        "minimum": 0.0,
                                        "maximum": 1.0,
                                    },
                                },
                                "additionalProperties": False,
                            },
                            "voice_id": {
                                "type": "string",
                                "const": "VOICE_ASSIGN_BY_MOOD",
                            },
                        },
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["future_selves"],
            "additionalProperties": False,
        },
    },
}

# ---------------------------------------------------------------------------
# User message template (runtime injection)
# ---------------------------------------------------------------------------

_USER_MESSAGE_TEMPLATE = """\
Generate {count} contrasting future self personas for the following person.

---

USER PROFILE:
- Core values: {core_values}
- Fears: {fears}
- Hidden tensions: {hidden_tensions}
- Decision style: {decision_style}
- Self-narrative: {self_narrative}
- Current dilemma: {current_dilemma}

---

CURRENT SELF (the selves you generate must feel genuinely different from this):
- Name: {current_self_name}
- Optimization goal: {current_self_optimization_goal}
- Tone of voice: {current_self_tone_of_voice}
- Worldview: {current_self_worldview}
- Core belief: {current_self_core_belief}
- Visual mood: {current_self_mood}

---

GENERATION RULES REMINDER:
- Generate exactly {count} future selves.
- Each self must optimize for a DIFFERENT value dimension — not variations of the same path.
- Each self must have a real trade-off: something genuinely gained, something genuinely lost.
- avatar_prompt must be 3-5 sentences describing a real person in a real setting (cinematic, editorial).
- voice_id must always be the literal string "VOICE_ASSIGN_BY_MOOD".
- avatar_url must always be null.
- No two selves should share the same primary_color or mood.
- Respond ONLY with the JSON object. No text before or after.\
"""

# ---------------------------------------------------------------------------
# Secondary generation template (for branching from a chosen path)
# ---------------------------------------------------------------------------

_SECONDARY_MESSAGE_TEMPLATE = """\
Generate {count} contrasting future scenarios for a person who chose a specific life path {time_ago}.

This person made a major decision and has been living with it. Generate futures exploring how that SAME initial choice evolved differently based on life factors (relationships, health, opportunities, unexpected events, trade-off consequences).

---

PARENT PATH CHOSEN:
- Name: {parent_name}
- What they optimized for: {parent_optimization_goal}
- Their worldview: {parent_worldview}
- Their core belief: {parent_core_belief}
- What they traded off: {parent_trade_off}
- Visual mood: {parent_mood}

---

ORIGINAL USER PROFILE (for context):
- Core values: {core_values}
- Fears: {fears}
- Hidden tensions: {hidden_tensions}

---

GENERATION RULES:
- Generate exactly {count} future selves, all starting from the SAME chosen path ("{parent_name}")
- Explore how the initial choice's **consequences played out differently** based on:
  * How relationships evolved (thrived, struggled, unexpected connections)
  * How career/goals progressed (accelerated, plateaued, pivoted)
  * How trade-offs manifested (worse than expected, better than expected, different than expected)
  * External factors (health, economy, opportunities, crises)
- Each self should feel like "{parent_name} + {time_ago} + different life circumstances"
- Names should be: "Self Who [parent choice] and [what happened]"
  Example: "Self Who Took the Singapore Move and Found Unexpected Community"
- Trade-offs should reference the parent choice and what happened since
- Do NOT rehash the original dilemma — focus on what happened AFTER the choice
- Visual mood should reflect the emotional outcome (not copy parent mood: {parent_mood})
- All standard technical rules apply (voice_id="VOICE_ASSIGN_BY_MOOD", avatar_url=null, unique colors/moods)
- Respond ONLY with the JSON object. No text before or after.\
"""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class FutureSelfGenerator:
    """
    Stateless engine — receives profile + current self, calls the Mistral
    Future Self agent, assigns ElevenLabs voice IDs, and returns SelfCards.
    """

    # Adjacent moods to try when the primary mood voice is already in use
    MOOD_FALLBACK_CHAINS: dict[str, list[str]] = {
        "elevated":  ["sharp", "intense", "calm"],
        "warm":      ["grounded", "calm", "ethereal"],
        "sharp":     ["elevated", "intense", "grounded"],
        "grounded":  ["warm", "calm", "sharp"],
        "ethereal":  ["calm", "warm", "elevated"],
        "intense":   ["sharp", "elevated", "grounded"],
        "calm":      ["grounded", "warm", "ethereal"],
    }

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = Mistral(api_key=self.settings.mistral_api_key)

    async def generate(
        self,
        user_profile: UserProfile,
        current_self: SelfCard,
        count: int = 2,
    ) -> list[SelfCard]:
        """
        Generate `count` future self SelfCards for the given user.

        Raises:
            ValueError: if Mistral returns unparseable or schema-invalid JSON.
            Exception: propagates Mistral API errors as-is.
        """
        user_message = self._build_user_message(user_profile, current_self, count)

        response = await self.client.agents.complete_async(
            agent_id=self.settings.mistral_agent_id_future_self,
            messages=[{"role": "user", "content": user_message}],
            response_format=FUTURE_SELF_RESPONSE_FORMAT, # pyright: ignore[reportArgumentType]
        )

        raw_json = response.choices[0].message.content
        if not raw_json:
            raise ValueError("Mistral returned an empty response")

        try:
            raw_output = RawFutureSelvesOutput.model_validate_json(raw_json) # pyright: ignore[reportArgumentType]
        except Exception as exc:
            raise ValueError(
                f"Mistral output failed schema validation: {exc}\nRaw output: {raw_json[:500]}"
            ) from exc

        return self._assign_voices_and_finalize(raw_output.future_selves)

    async def generate_secondary(
        self,
        parent_self: SelfCard,
        user_profile: UserProfile,
        count: int = 2,
        time_horizon: str = "2-3 years",
    ) -> list[SelfCard]:
        """
        Generate secondary futures exploring how a chosen path evolved.
        
        This creates branching scenarios from a parent choice, exploring how
        the same initial decision led to different outcomes based on life factors.
        
        Args:
            parent_self: The chosen future self to branch from
            user_profile: Original user profile for context
            count: Number of secondary futures to generate (2-3)
            time_horizon: How far into the future (for prompt context)
        
        Returns:
            List of secondary SelfCards with parent_self_id and depth_level set
        
        Raises:
            ValueError: if Mistral returns unparseable or schema-invalid JSON
            Exception: propagates Mistral API errors as-is
        """
        user_message = self._build_secondary_message(
            parent_self, user_profile, count, time_horizon
        )

        response = await self.client.agents.complete_async(
            agent_id=self.settings.mistral_agent_id_future_self,
            messages=[{"role": "user", "content": user_message}],
            response_format=FUTURE_SELF_RESPONSE_FORMAT, # pyright: ignore[reportArgumentType]
        )

        raw_json = response.choices[0].message.content
        if not raw_json:
            raise ValueError("Mistral returned an empty response")

        try:
            raw_output = RawFutureSelvesOutput.model_validate_json(raw_json) # pyright: ignore[reportArgumentType]
        except Exception as exc:
            raise ValueError(
                f"Mistral output failed schema validation: {exc}\nRaw output: {raw_json[:500]}"
            ) from exc

        # Assign voices and set tree metadata
        result = self._assign_voices_and_finalize(raw_output.future_selves)
        
        # Set parent and depth for tree navigation
        for card in result:
            card.parent_self_id = parent_self.id
            card.depth_level = parent_self.depth_level + 1
        
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_user_message(
        self,
        profile: UserProfile,
        current_self: SelfCard,
        count: int,
    ) -> str:
        return _USER_MESSAGE_TEMPLATE.format(
            count=count,
            core_values=", ".join(profile.core_values),
            fears=", ".join(profile.fears),
            hidden_tensions=" | ".join(profile.hidden_tensions),
            decision_style=profile.decision_style,
            self_narrative=profile.self_narrative,
            current_dilemma=profile.current_dilemma,
            current_self_name=current_self.name,
            current_self_optimization_goal=current_self.optimization_goal,
            current_self_tone_of_voice=current_self.tone_of_voice,
            current_self_worldview=current_self.worldview,
            current_self_core_belief=current_self.core_belief,
            current_self_mood=current_self.visual_style.mood,
        )

    def _build_secondary_message(
        self,
        parent_self: SelfCard,
        profile: UserProfile,
        count: int,
        time_horizon: str,
    ) -> str:
        """Build prompt for secondary generation from a parent choice"""
        return _SECONDARY_MESSAGE_TEMPLATE.format(
            count=count,
            time_ago=time_horizon,
            parent_name=parent_self.name,
            parent_optimization_goal=parent_self.optimization_goal,
            parent_worldview=parent_self.worldview,
            parent_core_belief=parent_self.core_belief,
            parent_trade_off=parent_self.trade_off,
            parent_mood=parent_self.visual_style.mood,
            core_values=", ".join(profile.core_values),
            fears=", ".join(profile.fears),
            hidden_tensions=" | ".join(profile.hidden_tensions),
        )

    def _assign_voices_and_finalize(
        self, raw_selves: list[RawSelfCard]
    ) -> list[SelfCard]:
        used_voice_ids: set[str] = set()
        result: list[SelfCard] = []

        for raw in raw_selves:
            voice_id = self._assign_voice(raw.visual_style.mood, used_voice_ids)
            card = SelfCard(
                id=f"self_future_{uuid.uuid4().hex[:8]}",
                type="future",
                name=raw.name,
                optimization_goal=raw.optimization_goal,
                tone_of_voice=raw.tone_of_voice,
                worldview=raw.worldview,
                core_belief=raw.core_belief,
                trade_off=raw.trade_off,
                avatar_prompt=raw.avatar_prompt,
                avatar_url=None,
                visual_style=VisualStyle(
                    primary_color=raw.visual_style.primary_color,
                    accent_color=raw.visual_style.accent_color,
                    mood=raw.visual_style.mood,  # type: ignore[arg-type]
                    glow_intensity=raw.visual_style.glow_intensity,
                ),
                voice_id=voice_id,
            )
            result.append(card)

        return result

    def _assign_voice(self, mood: str, used_voice_ids: set[str]) -> str:
        """
        Assign a unique ElevenLabs voice ID from the pool based on mood.

        Priority: pool[mood] → fallback chain → default voice.
        Guarantees each self in the batch gets a distinct voice ID.
        """
        voice_pool = self.settings.elevenlabs_voice_pool
        fallback_chain = self.MOOD_FALLBACK_CHAINS.get(mood, [])

        for candidate_mood in [mood, *fallback_chain]:
            candidate_id = voice_pool.get(candidate_mood)
            if candidate_id and candidate_id not in used_voice_ids:
                used_voice_ids.add(candidate_id)
                return candidate_id

        # Last resort: default voice (interview agent voice)
        return self.settings.elevenlabs_default_voice_id
