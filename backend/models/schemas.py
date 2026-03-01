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


# ---------------------------------------------------------------------------
# Onboarding profile structures
# ---------------------------------------------------------------------------

class CareerProfile(BaseModel):
    model_config = _camel_config()

    job_title: str = ""
    industry: str = ""
    seniority_level: str = ""  # e.g., "entry", "mid", "senior", "executive"
    years_experience: int = 0
    current_company: str = ""
    career_goal: str = ""
    job_satisfaction: str = ""  # 1-10 or descriptor
    main_challenges: list[str] = Field(default_factory=list)


class FinancialProfile(BaseModel):
    model_config = _camel_config()

    income_level: str = ""  # e.g., "50-75k", "75-100k", "100-150k", "150k+"
    financial_goals: list[str] = Field(default_factory=list)
    money_mindset: str = ""  # e.g., "security-focused", "growth-oriented", "balanced"
    risk_tolerance: str = ""  # e.g., "low", "medium", "high"
    main_financial_concern: str = ""


class PersonalProfile(BaseModel):
    model_config = _camel_config()

    hobbies: list[str] = Field(default_factory=list)
    daily_routines: list[str] = Field(default_factory=list)
    main_interests: list[str] = Field(default_factory=list)
    relationships: str = ""  # e.g., "married", "single", "in partnership"
    key_relationships: list[str] = Field(default_factory=list)
    personal_values: list[str] = Field(default_factory=list)


class HealthProfile(BaseModel):
    model_config = _camel_config()

    physical_health: str = ""  # e.g., "good", "fair", "needs attention"
    mental_health: str = ""  # e.g., "stable", "managing stress", "challenged"
    sleep_quality: str = ""  # e.g., "good", "fair", "poor"
    exercise_frequency: str = ""  # e.g., "daily", "3-4x/week", "irregular"
    stress_level: str = ""  # 1-10 or descriptor
    health_goals: list[str] = Field(default_factory=list)


class LifeSituationProfile(BaseModel):
    model_config = _camel_config()

    current_location: str = ""
    life_stage: str = ""  # e.g., "early career", "establishing self", "mid-career pivot", "advancement phase"
    major_responsibilities: list[str] = Field(default_factory=list)
    recent_transitions: list[str] = Field(default_factory=list)
    upcoming_changes: list[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    model_config = _camel_config()

    id: str
    core_values: list[str]
    fears: list[str]
    hidden_tensions: list[str]
    decision_style: str
    self_narrative: str
    current_dilemma: str
    
    # Extended profile sections (optional, populated during onboarding)
    career: CareerProfile = Field(default_factory=CareerProfile)
    financial: FinancialProfile = Field(default_factory=FinancialProfile)
    personal: PersonalProfile = Field(default_factory=PersonalProfile)
    health: HealthProfile = Field(default_factory=HealthProfile)
    life_situation: LifeSituationProfile = Field(default_factory=LifeSituationProfile)


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
# Onboarding request/response models
# ---------------------------------------------------------------------------

class InterviewStartRequest(BaseModel):
    model_config = _camel_config()

    session_id: str
    user_name: str = "User"


class InterviewReplyRequest(BaseModel):
    model_config = _camel_config()

    session_id: str
    user_message: str
    stream: bool = Field(
        default=False,
        description="When true, clients should use /interview/reply-stream for SSE token streaming.",
    )


class InterviewStatusResponse(BaseModel):
    model_config = _camel_config()

    session_id: str
    profile_completeness: float = Field(ge=0.0, le=1.0, description="0-1 indicating % profile filled")
    extracted_fields: dict[str, bool]  # field_name -> is_extracted
    current_dilemma: str | None = None
    is_ready_for_generation: bool = False


class InterviewReplyResponse(BaseModel):
    model_config = _camel_config()

    session_id: str
    agent_message: str
    profile_completeness: float = Field(ge=0.0, le=1.0)
    extracted_fields: dict[str, bool]


class InterviewCompleteRequest(BaseModel):
    model_config = _camel_config()

    session_id: str
    user_confirmed_dilemma: str | None = None  # Confirm or override extracted dilemma


class InterviewCompleteResponse(BaseModel):
    model_config = _camel_config()

    session_id: str
    user_profile: UserProfile
    current_self: SelfCard
    ready_for_future_generation: bool = True
    message: str = "Onboarding complete! Ready to explore future selves."


# ---------------------------------------------------------------------------
# Profile extraction internal schema (for Mistral)
# ---------------------------------------------------------------------------

class ExtractedProfileData(BaseModel):
    """
    Incremental profile extraction output from Mistral.
    Confidence scores help track data quality and guide follow-up questions.
    """
    model_config = ConfigDict(populate_by_name=True)
    
    career: CareerProfile = Field(default_factory=CareerProfile)
    career_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    financial: FinancialProfile = Field(default_factory=FinancialProfile)
    financial_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    personal: PersonalProfile = Field(default_factory=PersonalProfile)
    personal_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    health: HealthProfile = Field(default_factory=HealthProfile)
    health_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    life_situation: LifeSituationProfile = Field(default_factory=LifeSituationProfile)
    life_situation_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    psychology: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "core_values": [],
            "fears": [],
            "hidden_tensions": [],
        }
    )
    psychology_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    decision_style: str = ""
    decision_style_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    self_narrative: str = ""
    self_narrative_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    current_dilemma: str = ""
    dilemma_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Current Self auto-generation schema (for Mistral)
# ---------------------------------------------------------------------------

class CurrentSelfGenerationSchema(BaseModel):
    """
    JSON schema for Mistral to auto-generate CurrentSelf from UserProfile.
    Uses profile data to derive avatar, tone, worldview, core belief, trade-off.
    """
    current_self: dict = Field(
        description="Generated CurrentSelf card derived from user profile"
    )


class RawExtractedProfileData(BaseModel):
    career: dict = Field(default_factory=dict)
    career_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    financial: dict = Field(default_factory=dict)
    financial_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    personal: dict = Field(default_factory=dict)
    personal_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    health: dict = Field(default_factory=dict)
    health_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    life_situation: dict = Field(default_factory=dict)
    life_situation_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    psychology: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "core_values": [],
            "fears": [],
            "hidden_tensions": [],
        }
    )
    psychology_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    decision_style: str = ""
    decision_style_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    self_narrative: str = ""
    self_narrative_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    current_dilemma: str = ""
    dilemma_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RawCurrentSelfOutput(BaseModel):
    name: str
    optimization_goal: str
    tone_of_voice: str
    worldview: str
    core_belief: str
    trade_off: str
    avatar_prompt: str
    visual_style: dict


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
