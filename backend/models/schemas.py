from __future__ import annotations

import time
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


# ---------------------------------------------------------------------------
# Shared config helper
# ---------------------------------------------------------------------------

def _camel_config() -> ConfigDict:
    return ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------

class VisualStyle(BaseModel):
    model_config = _camel_config()

    primary_color: str
    accent_color: str
    mood: Literal["elevated", "warm", "sharp", "grounded", "ethereal", "intense", "calm"]
    glow_intensity: float = Field(ge=0.0, le=1.0)


class SelfCard(BaseModel):
    model_config = _camel_config()

    id: str = Field(default_factory=lambda: f"self_{uuid.uuid4().hex[:8]}")
    type: Literal["current", "future"]
    name: str
    optimization_goal: str
    tone_of_voice: str
    worldview: str
    core_belief: str
    trade_off: str
    avatar_prompt: str = ""
    avatar_url: str | None = None
    visual_style: VisualStyle
    voice_id: str = "VOICE_ASSIGN_BY_MOOD"
    
    # Tree navigation fields for multi-level branching
    parent_self_id: str | None = Field(
        default=None,
        description="ID of parent self (None for root level)"
    )
    depth_level: int = Field(
        default=0,
        ge=0,
        description="Branch depth: 0=current self, 1=initial choice, 2+=secondary exploration"
    )
    children_ids: list[str] = Field(
        default_factory=list,
        description="IDs of generated child selves"
    )


class UserProfile(BaseModel):
    model_config = _camel_config()

    id: str
    core_values: list[str]
    fears: list[str]
    hidden_tensions: list[str]
    decision_style: str
    self_narrative: str
    current_dilemma: str


# ---------------------------------------------------------------------------
# Request / Response models for POST /future-self/generate
# ---------------------------------------------------------------------------

class GenerateFutureSelvesRequest(BaseModel):
    model_config = _camel_config()

    session_id: str
    count: int = Field(default=2, ge=2, le=3)
    parent_self_id: str | None = Field(
        default=None,
        description="Generate secondary futures from this parent (None = root level)"
    )
    time_horizon: str | None = Field(
        default=None,
        description="Override the default time horizon (e.g. '5 years', '2-3 years')"
    )


class GenerateFutureSelvesResponse(BaseModel):
    model_config = _camel_config()

    session_id: str
    future_self_options: list[SelfCard]
    generated_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Internal raw models — parse Mistral output before voice assignment
# These use snake_case directly (no alias) because we control serialization.
# ---------------------------------------------------------------------------

class RawVisualStyle(BaseModel):
    primary_color: str
    accent_color: str
    mood: str
    glow_intensity: float


class RawSelfCard(BaseModel):
    id: str | None = None  # Not used - we generate UUIDs ourselves
    type: Literal["future"]
    name: str
    optimization_goal: str
    tone_of_voice: str
    worldview: str
    core_belief: str
    trade_off: str
    avatar_prompt: str
    avatar_url: None  # enforced null from Mistral output
    visual_style: RawVisualStyle
    voice_id: str     # expected to be "VOICE_ASSIGN_BY_MOOD"


class RawFutureSelvesOutput(BaseModel):
    future_selves: list[RawSelfCard]


# ---------------------------------------------------------------------------
# Request / Response models for POST /conversation/reply
# ---------------------------------------------------------------------------

class ConversationMessage(BaseModel):
    model_config = _camel_config()

    role: Literal["user", "assistant"]
    content: str


class ConversationReplyRequest(BaseModel):
    model_config = _camel_config()

    session_id: str
    self_id: str
    message: str
    history: list[ConversationMessage] = Field(
        default_factory=list,
        description="All prior turns, oldest first. Client owns history — send full history on every request.",
    )


class ConversationReplyResponse(BaseModel):
    model_config = _camel_config()

    session_id: str
    self_id: str
    branch_name: str
    reply: str
    history: list[ConversationMessage] = Field(
        description="Updated history including the new user turn and assistant reply. Replace client-side history with this value.",
    )
