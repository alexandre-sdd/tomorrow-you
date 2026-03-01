"""
Current Self Auto-Generator Engine

Automatically generates a CurrentSelf SelfCard from completed UserProfile.
Derives persona characteristics, visual style, and voice from profile data.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from mistralai import Mistral

from backend.config.settings import get_settings
from backend.models.schemas import (
    RawCurrentSelfOutput,
    SelfCard,
    UserProfile,
    VisualStyle,
)

# ---------------------------------------------------------------------------
# JSON schema for current self generation (Mistral enforcement)
# ---------------------------------------------------------------------------

CURRENT_SELF_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "current_self_generation",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "const": "Current Self"},
                "optimization_goal": {
                    "type": "string",
                    "description": "What this person is optimizing for given their values and constraints",
                },
                "tone_of_voice": {
                    "type": "string",
                    "description": "How this person speaks and presents: tone, mannerisms, emotional openness",
                },
                "worldview": {
                    "type": "string",
                    "description": "How they see the world: beliefs about how things work, how decisions get made",
                },
                "core_belief": {
                    "type": "string",
                    "description": "One core belief that drives their decisions and actions",
                },
                "trade_off": {
                    "type": "string",
                    "description": "The trade-off they're currently making: what they're optimizing for vs. what they're sacrificing",
                },
                "avatar_prompt": {
                    "type": "string",
                    "description": "Detailed visual description for avatar generation (cinema style, age, clothing, expression, location cues, mood)",
                },
                "visual_style": {
                    "type": "object",
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
                    "required": ["primary_color", "accent_color", "mood", "glow_intensity"],
                    "additionalProperties": False,
                },
            },
            "required": [
                "name",
                "optimization_goal",
                "tone_of_voice",
                "worldview",
                "core_belief",
                "trade_off",
                "avatar_prompt",
                "visual_style",
            ],
            "additionalProperties": False,
        },
    },
}


# ---------------------------------------------------------------------------
# Generation context and result
# ---------------------------------------------------------------------------

@dataclass
class CurrentSelfGenerationContext:
    """Input for current self auto-generation."""
    session_id: str
    user_profile: UserProfile


@dataclass
class CurrentSelfGenerationResult:
    """Output from current self generation."""
    session_id: str
    current_self: SelfCard


# ---------------------------------------------------------------------------
# Current Self Auto-Generator
# ---------------------------------------------------------------------------

class CurrentSelfAutoGeneratorEngine:
    """
    Auto-generates CurrentSelf SelfCard from UserProfile.
    Uses Mistral to derive persona characteristics from profile data.
    """

    def __init__(self, mistral_client: Mistral | None = None):
        self.client = mistral_client or Mistral(
            api_key=get_settings().mistral_api_key
        )
        self.settings = get_settings()

    async def generate(
        self, ctx: CurrentSelfGenerationContext
    ) -> CurrentSelfGenerationResult:
        """
        Auto-generate CurrentSelf from profile.
        
        Args:
            ctx: Profile and session context
        
        Returns:
            CurrentSelfGenerationResult with generated SelfCard
            
        Raises:
            ValueError: if Mistral returns invalid JSON or schema violation
        """
        # Build generation prompt
        prompt = self._build_generation_prompt(ctx.user_profile)

        if not self.settings.mistral_agent_id_current_self_generation.strip():
            raise ValueError(
                "MISTRAL_AGENT_ID_CURRENT_SELF_GENERATION is not configured. "
                "Set it in .env to use the preconfigured current-self generation agent."
            )

        # Call Mistral agent with JSON schema enforcement
        response = await self.client.agents.complete_async(
            agent_id=self.settings.mistral_agent_id_current_self_generation,
            messages=[{"role": "user", "content": prompt}],
            response_format=CURRENT_SELF_RESPONSE_FORMAT,  # pyright: ignore
        )
        
        raw_json = response.choices[0].message.content
        if not raw_json:
            raise ValueError("Mistral returned empty current self generation")
        
        # Parse and validate
        try:
            raw_output = RawCurrentSelfOutput.model_validate_json(raw_json)  # pyright: ignore
        except Exception as exc:
            raise ValueError(
                f"Current self generation schema validation failed: {exc}\n"
                f"Raw output: {raw_json[:500]}"
            ) from exc
        
        # Build SelfCard with voice assignment
        self_card = self._build_self_card(ctx.user_profile, raw_output)
        
        return CurrentSelfGenerationResult(
            session_id=ctx.session_id,
            current_self=self_card,
        )

    def _build_generation_prompt(self, profile: UserProfile) -> str:
        """Build prompt for current self generation."""
        profile_summary = self._summarize_profile(profile)
        
        return f"""\
Generate a CurrentSelf persona card based on this user's profile and life situation.

PROFILE SUMMARY:
{profile_summary}

TASK:
Derive a CurrentSelf SelfCard that represents this person *as they are now*, wrestling with their central dilemma. This is their grounded, present-moment self—the perspective they're viewing their decision from before exploring future possibilities.

GUIDELINES:
1. **optimization_goal**: What are they trying to optimize for right now? Usually a balance or juggling act (e.g., "Balance career growth, financial upside, marital stability, and long-term life coherence")

2. **tone_of_voice**: How does this person present? Derive from their decision_style and personality hints in the profile. Are they analytical, measured, warm, restless, grounded? Include emotional tone.

3. **worldview**: How do they see the world and decisions? Draw from their hidden_tensions and self_narrative. What's their underlying philosophy?

4. **core_belief**: Distill to ONE belief that drives their decision-making. This should be distinct and personal.

5. **trade_off**: What trade-off are they currently making? What are they optimizing FOR vs. what are they sacrificing? This should reflect their current tensions.

6. **avatar_prompt**: Detailed visual description (~60 words). Include:
   - Realistic age and appearance cues from life_stage
   - Current location or setting from current_location
   - Clothing/style reflecting career_goal and income_level
   - Facial expression/body language reflecting their emotional state (slightly tense if conflicted, grounded if resolved, etc.)
   - Cinematic portrait style, emotionally nuanced, premium product photography

7. **visual_style**:
   - **primary_color**: Hex color reflecting their decision_style and mood (analytical → cool blues, warm personality → warm earth tones)
   - **accent_color**: Complementary color
   - **mood**: One of: elevated, warm, sharp, grounded, ethereal, intense, calm
   - **glow_intensity**: 0-1 scale. High if excited/resolved (0.6+), medium if conflicted (0.3-0.5), low if struggling

For voice assignment, use the mood to guide tone (will be assigned post-generation).

Return JSON matching the schema.
"""

    def _summarize_profile(self, profile: UserProfile) -> str:
        """Create readable summary of profile for generation prompt."""
        return f"""\
**Life Situation**:
- Location: {profile.life_situation.current_location or "Not specified"}
- Life stage: {profile.life_situation.life_stage or "Not specified"}
- Responsibilities: {', '.join(profile.life_situation.major_responsibilities) if profile.life_situation.major_responsibilities else "Not specified"}

**Relationships**:
- Status: {profile.personal.relationships or "Not specified"}
- Key people: {', '.join(profile.personal.key_relationships) if profile.personal.key_relationships else "Not specified"}

**Work**:
- Title: {profile.career.job_title or "Not specified"}
- Industry: {profile.career.industry or "Not specified"}
- Goal: {profile.career.career_goal or "Not specified"}
- Satisfaction: {profile.career.job_satisfaction or "Not specified"}

**Financial**:
- Income: {profile.financial.income_level or "Not specified"}
- Mindset: {profile.financial.money_mindset or "Not specified"}
- Risk tolerance: {profile.financial.risk_tolerance or "Not specified"}

**Psychology**:
- Core values: {', '.join(profile.core_values) if profile.core_values else "Not specified"}
- Fears: {', '.join(profile.fears) if profile.fears else "Not specified"}
- Hidden tensions: {'; '.join(profile.hidden_tensions) if profile.hidden_tensions else "Not specified"}
- Decision style: {profile.decision_style or "Not specified"}

**Self Understanding**:
- Self narrative: {profile.self_narrative or "Not specified"}

**Central Dilemma**:
{profile.current_dilemma or "Not fully articulated yet"}
"""

    def _build_self_card(
        self, profile: UserProfile, raw_output: RawCurrentSelfOutput
    ) -> SelfCard:
        """Build SelfCard with voice assignment from raw Mistral output."""
        # Parse visual style
        visual_style_data = raw_output.visual_style
        visual_style = VisualStyle(
            primary_color=visual_style_data.get("primary_color", "#1F3A5F"),
            accent_color=visual_style_data.get("accent_color", "#D6E4F0"),
            mood=visual_style_data.get("mood", "calm"),
            glow_intensity=float(visual_style_data.get("glow_intensity", 0.5)),
        )
        
        # Assign voice based on mood
        voice_id = self._assign_voice_by_mood(visual_style.mood)
        
        # Create SelfCard
        self_card = SelfCard(
            id=f"self_current_{uuid.uuid4().hex[:8]}",
            type="current",
            name=raw_output.name,
            optimization_goal=raw_output.optimization_goal,
            tone_of_voice=raw_output.tone_of_voice,
            worldview=raw_output.worldview,
            core_belief=raw_output.core_belief,
            trade_off=raw_output.trade_off,
            avatar_prompt=raw_output.avatar_prompt,
            avatar_url=None,
            visual_style=visual_style,
            voice_id=voice_id,
            parent_self_id=None,
            depth_level=0,
            children_ids=[],
        )
        
        return self_card

    def _assign_voice_by_mood(self, mood: str) -> str:
        """
        Assign ElevenLabs voice ID based on visual mood.
        Uses mood → voice pool mapping from settings.
        """
        voice_pool = self.settings.elevenlabs_voice_pool
        
        # Try exact mood match first
        if mood in voice_pool:
            return voice_pool[mood]
        
        # Fallback to default
        return self.settings.elevenlabs_default_voice_id
