from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

from mistralai import Mistral

from backend.config.runtime import get_runtime_config
from backend.config.settings import get_settings
from backend.models.schemas import (
    RawFutureSelvesOutput,
    RawSelfCard,
    SelfCard,
    UserProfile,
    VisualStyle,
)

_runtime_fg = get_runtime_config().future_generation

# ---------------------------------------------------------------------------
# Content-hashed ID generation
# ---------------------------------------------------------------------------

def hash_id(name: str, parent_id: str | None, timestamp: float) -> str:
    """
    Generate a short deterministic ID from content.

    Uses SHA-256 of (name + parent_id + timestamp) truncated to 10 hex chars
    (40 bits ≈ 1 trillion values). Virtually collision-free within a session.
    """
    raw = f"{name}|{parent_id or ''}|{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:10]


# ---------------------------------------------------------------------------
# Generation context — single contract for all depths
# ---------------------------------------------------------------------------

@dataclass
class GenerationContext:
    """
    Everything the engine needs to generate personas at any depth.

    Callers (the router) are responsible for resolving ancestor summaries
    and conversation excerpts before constructing this object.
    """
    user_profile: UserProfile
    current_self: SelfCard
    count: int = 2

    # Depth-specific (None / empty at root level)
    parent_self: SelfCard | None = None
    ancestor_summary: str = ""
    conversation_excerpts: list[str] = field(default_factory=list)
    sibling_names: list[str] = field(default_factory=list)

    # Derived / overridable
    depth: int = 0
    time_horizon: str = _runtime_fg.default_time_horizon

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
# Unified prompt template — adapts by depth, injects conversation context
# ---------------------------------------------------------------------------

_GENERATION_TEMPLATE = """\
Generate {count} contrasting future self personas for the following person.

{depth_framing}

---

USER PROFILE:
- Core values: {core_values}
- Fears: {fears}
- Hidden tensions: {hidden_tensions}
- Decision style: {decision_style}
- Self-narrative: {self_narrative}
- Current dilemma: {current_dilemma}

---

{anchor_section}

{parent_section}

{ancestor_section}

{conversation_section}

{sibling_section}

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

_ANCHOR_SECTION = """\
CURRENT SELF (the anchor — selves you generate must feel genuinely different from this):
- Name: {name}
- Optimization goal: {optimization_goal}
- Tone of voice: {tone_of_voice}
- Worldview: {worldview}
- Core belief: {core_belief}
- Visual mood: {mood}\
"""

_PARENT_SECTION = """\
PARENT PATH CHOSEN (the immediate decision this person already made):
- Name: {name}
- What they optimized for: {optimization_goal}
- Their worldview: {worldview}
- Their core belief: {core_belief}
- What they traded off: {trade_off}
- Visual mood: {mood}\
"""

_ROOT_DEPTH_FRAMING = """\
This person stands at a crossroads. Generate futures that diverge from their \
current self — each representing a genuinely different life path.\
"""

_BRANCH_DEPTH_FRAMING = """\
Generate {count} contrasting future scenarios for a person who chose a specific \
life path {time_horizon} ago.

This person made a major decision and has been living with it. Generate futures \
exploring how that SAME initial choice evolved differently based on life factors \
(relationships, health, opportunities, unexpected events, trade-off consequences).

Each self should feel like "{parent_name} + {time_horizon} + different life circumstances".
- Names should be: "Self Who [parent choice] and [what happened]"
- Trade-offs should reference the parent choice and what happened since
- Do NOT rehash the original dilemma — focus on what happened AFTER the choice
- Visual mood should reflect the emotional outcome (not copy parent mood: {parent_mood})\
"""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class FutureSelfGenerator:
    """
    Stateless engine — builds a depth-aware prompt from a GenerationContext,
    calls the Mistral Future Self agent, assigns ElevenLabs voice IDs,
    and returns SelfCards with content-hashed IDs.

    A single ``generate(ctx)`` method handles every depth level.
    The caller (router) is responsible for resolving ancestor summaries,
    conversation excerpts, and sibling names before calling this.
    """

    # Adjacent moods to try when the primary mood voice is already in use
    MOOD_FALLBACK_CHAINS: dict[str, list[str]] = _runtime_fg.mood_fallback_chains

    # Default time horizons by depth (overridable via GenerationContext)
    DEFAULT_TIME_HORIZONS: dict[int, str] = _runtime_fg.default_time_horizons_by_depth

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = Mistral(api_key=self.settings.mistral_api_key)

    # ------------------------------------------------------------------
    # Public API — single entry point for all depths
    # ------------------------------------------------------------------

    async def generate(self, ctx: GenerationContext) -> list[SelfCard]:
        """
        Generate ``ctx.count`` future self SelfCards at any depth.

        Works for root level (ctx.parent_self is None, ctx.depth == 0)
        and for branching at any depth (ctx.parent_self set, ctx.depth >= 1).

        Returns:
            List of SelfCards with content-hashed IDs, tree metadata
            (parent_self_id, depth_level) already set, and voices assigned.

        Raises:
            ValueError: if Mistral returns unparseable or schema-invalid JSON.
            Exception: propagates Mistral API errors as-is.
        """
        user_message = self._build_message(ctx)

        response = await self.client.agents.complete_async(
            agent_id=self.settings.mistral_agent_id_future_self,
            messages=[{"role": "user", "content": user_message}],
            response_format=FUTURE_SELF_RESPONSE_FORMAT,  # pyright: ignore[reportArgumentType]
        )

        raw_json = response.choices[0].message.content
        if not raw_json:
            raise ValueError("Mistral returned an empty response")

        try:
            raw_output = RawFutureSelvesOutput.model_validate_json(raw_json)  # pyright: ignore[reportArgumentType]
        except Exception as exc:
            raise ValueError(
                f"Mistral output failed schema validation: {exc}\n"
                f"Raw output: {raw_json[:500]}"
            ) from exc

        import time as _time
        now = _time.time()

        return self._assign_voices_and_finalize(
            raw_output.future_selves,
            parent_id=ctx.parent_self.id if ctx.parent_self else None,
            depth=ctx.depth + 1 if ctx.parent_self else 1,
            timestamp=now,
        )

    # ------------------------------------------------------------------
    # Prompt builder — single method, conditional sections
    # ------------------------------------------------------------------

    def _build_message(self, ctx: GenerationContext) -> str:
        """Build a depth-aware prompt from the GenerationContext."""
        profile = ctx.user_profile

        # --- Depth framing ---
        if ctx.parent_self is None:
            depth_framing = _ROOT_DEPTH_FRAMING
        else:
            depth_framing = _BRANCH_DEPTH_FRAMING.format(
                count=ctx.count,
                time_horizon=ctx.time_horizon,
                parent_name=ctx.parent_self.name,
                parent_mood=ctx.parent_self.visual_style.mood,
            )

        # --- Anchor (current self — always present) ---
        anchor_section = _ANCHOR_SECTION.format(
            name=ctx.current_self.name,
            optimization_goal=ctx.current_self.optimization_goal,
            tone_of_voice=ctx.current_self.tone_of_voice,
            worldview=ctx.current_self.worldview,
            core_belief=ctx.current_self.core_belief,
            mood=ctx.current_self.visual_style.mood,
        )

        # --- Parent (only at depth >= 1) ---
        parent_section = ""
        if ctx.parent_self is not None:
            parent_section = _PARENT_SECTION.format(
                name=ctx.parent_self.name,
                optimization_goal=ctx.parent_self.optimization_goal,
                worldview=ctx.parent_self.worldview,
                core_belief=ctx.parent_self.core_belief,
                trade_off=ctx.parent_self.trade_off,
                mood=ctx.parent_self.visual_style.mood,
            )

        # --- Ancestor summary (depth >= 2) ---
        ancestor_section = ""
        if ctx.ancestor_summary:
            ancestor_section = (
                "ANCESTOR CHAIN (summarized for context — this person's lineage of choices):\n"
                f"{ctx.ancestor_summary}"
            )

        # --- Conversation insights ---
        conversation_section = ""
        if ctx.conversation_excerpts:
            excerpts = "\n".join(f"- {e}" for e in ctx.conversation_excerpts)
            conversation_section = (
                "CONVERSATION INSIGHTS (things revealed while talking to previously generated selves):\n"
                f"{excerpts}\n"
                "Use these revealed preferences and emotions to shape the generated personas."
            )

        # --- Sibling dedup ---
        sibling_section = ""
        if ctx.sibling_names:
            names = ", ".join(ctx.sibling_names)
            sibling_section = (
                f"ALREADY GENERATED AT THIS LEVEL (avoid overlap): {names}"
            )

        return _GENERATION_TEMPLATE.format(
            count=ctx.count,
            depth_framing=depth_framing,
            core_values=", ".join(profile.core_values),
            fears=", ".join(profile.fears),
            hidden_tensions=" | ".join(profile.hidden_tensions),
            decision_style=profile.decision_style,
            self_narrative=profile.self_narrative,
            current_dilemma=profile.current_dilemma,
            anchor_section=anchor_section,
            parent_section=parent_section,
            ancestor_section=ancestor_section,
            conversation_section=conversation_section,
            sibling_section=sibling_section,
        )

    # ------------------------------------------------------------------
    # Voice assignment & finalization (now with hashed IDs)
    # ------------------------------------------------------------------

    def _assign_voices_and_finalize(
        self,
        raw_selves: list[RawSelfCard],
        *,
        parent_id: str | None,
        depth: int,
        timestamp: float,
    ) -> list[SelfCard]:
        used_voice_ids: set[str] = set()
        result: list[SelfCard] = []

        for raw in raw_selves:
            sid = hash_id(raw.name, parent_id, timestamp)
            voice_id = self._assign_voice(raw.visual_style.mood, used_voice_ids)
            card = SelfCard(
                id=sid,
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
                parent_self_id=parent_id,
                depth_level=depth,
                children_ids=[],
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
