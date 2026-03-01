"""
Profile Extractor Engine

Incremental profile extraction from interview transcripts using Mistral's
JSON schema enforcement. Updates user profile as interview progresses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from mistralai import Mistral

from backend.config.settings import get_settings
from backend.models.schemas import (
    CareerProfile,
    FinancialProfile,
    HealthProfile,
    LifeSituationProfile,
    PersonalProfile,
    RawExtractedProfileData,
    UserProfile,
)

# ---------------------------------------------------------------------------
# JSON schema for profile extraction (Mistral enforcement)
# ---------------------------------------------------------------------------

PROFILE_EXTRACTION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "profile_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "career": {
                    "type": "object",
                    "properties": {
                        "job_title": {"type": "string"},
                        "industry": {"type": "string"},
                        "seniority_level": {"type": "string"},
                        "years_experience": {"type": "integer", "minimum": 0},
                        "current_company": {"type": "string"},
                        "career_goal": {"type": "string"},
                        "job_satisfaction": {"type": "string"},
                        "main_challenges": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
                "career_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "financial": {
                    "type": "object",
                    "properties": {
                        "income_level": {"type": "string"},
                        "financial_goals": {"type": "array", "items": {"type": "string"}},
                        "money_mindset": {"type": "string"},
                        "risk_tolerance": {"type": "string"},
                        "main_financial_concern": {"type": "string"},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
                "financial_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "personal": {
                    "type": "object",
                    "properties": {
                        "hobbies": {"type": "array", "items": {"type": "string"}},
                        "daily_routines": {"type": "array", "items": {"type": "string"}},
                        "main_interests": {"type": "array", "items": {"type": "string"}},
                        "relationships": {"type": "string"},
                        "key_relationships": {"type": "array", "items": {"type": "string"}},
                        "personal_values": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
                "personal_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "health": {
                    "type": "object",
                    "properties": {
                        "physical_health": {"type": "string"},
                        "mental_health": {"type": "string"},
                        "sleep_quality": {"type": "string"},
                        "exercise_frequency": {"type": "string"},
                        "stress_level": {"type": "string"},
                        "health_goals": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
                "health_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "life_situation": {
                    "type": "object",
                    "properties": {
                        "current_location": {"type": "string"},
                        "life_stage": {"type": "string"},
                        "major_responsibilities": {"type": "array", "items": {"type": "string"}},
                        "recent_transitions": {"type": "array", "items": {"type": "string"}},
                        "upcoming_changes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
                "life_situation_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "psychology": {
                    "type": "object",
                    "properties": {
                        "core_values": {"type": "array", "items": {"type": "string"}},
                        "fears": {"type": "array", "items": {"type": "string"}},
                        "hidden_tensions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
                "psychology_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "decision_style": {"type": "string"},
                "decision_style_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "self_narrative": {"type": "string"},
                "self_narrative_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "current_dilemma": {"type": "string"},
                "dilemma_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": [
                "career",
                "career_confidence",
                "financial",
                "financial_confidence",
                "personal",
                "personal_confidence",
                "health",
                "health_confidence",
                "life_situation",
                "life_situation_confidence",
                "psychology",
                "psychology_confidence",
                "decision_style",
                "decision_style_confidence",
                "self_narrative",
                "self_narrative_confidence",
                "current_dilemma",
                "dilemma_confidence",
            ],
            "additionalProperties": False,
        },
    },
}


# ---------------------------------------------------------------------------
# Extraction context and result
# ---------------------------------------------------------------------------

@dataclass
class ExtractionContext:
    """Input data for profile extraction."""
    session_id: str
    transcript_history: list[dict[str, str]]  # [{role, content}, ...]
    current_profile: UserProfile | None = None


@dataclass
class ExtractionResult:
    """Output from profile extraction."""
    session_id: str
    extracted_profile: UserProfile
    profile_completeness: float
    extracted_fields: dict[str, bool]
    is_ready_for_current_self_gen: bool
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "extracted_profile": self.extracted_profile.model_dump(mode="json"),
            "profile_completeness": self.profile_completeness,
            "extracted_fields": self.extracted_fields,
            "is_ready_for_current_self_gen": self.is_ready_for_current_self_gen,
        }


# ---------------------------------------------------------------------------
# Profile Extractor Engine
# ---------------------------------------------------------------------------

class ProfileExtractorEngine:
    """
    Incremental profile extraction from interview transcripts.
    
    Works with Mistral's API using JSON schema enforcement.
    Merges new extractions with existing profile data.
    """

    def __init__(self, mistral_client: Mistral | None = None):
        self.client = mistral_client or Mistral(
            api_key=get_settings().mistral_api_key
        )
        self.settings = get_settings()

    async def extract(self, ctx: ExtractionContext) -> ExtractionResult:
        """
        Extract profile data from interview transcript.
        
        Args:
            ctx: Extraction context with session_id, transcript, current profile
        
        Returns:
            ExtractionResult with merged profile, completeness, readiness check
            
        Raises:
            ValueError: if Mistral returns invalid JSON or schema violation
        """
        # Build extraction prompt
        prompt = self._build_extraction_prompt(ctx)

        if not self.settings.mistral_agent_id_profile_extraction.strip():
            raise ValueError(
                "MISTRAL_AGENT_ID_PROFILE_EXTRACTION is not configured. "
                "Set it in .env to use the preconfigured profile extraction agent."
            )
        
        # Call Mistral with JSON schema enforcement
        response = await self.client.agents.complete_async(
            agent_id=self.settings.mistral_agent_id_profile_extraction,
            messages=[{"role": "user", "content": prompt}],
            response_format=PROFILE_EXTRACTION_RESPONSE_FORMAT,  # pyright: ignore
        )
        
        raw_json = response.choices[0].message.content
        if not raw_json:
            raise ValueError("Mistral returned empty profile extraction")
        
        # Parse and validate
        try:
            extracted_data = RawExtractedProfileData.model_validate_json(raw_json)  # pyright: ignore
        except Exception as exc:
            raise ValueError(
                f"Profile extraction schema validation failed: {exc}\n"
                f"Raw output: {raw_json[:500]}"
            ) from exc
        
        # Merge with existing profile
        merged_profile = self._merge_profiles(ctx.current_profile, extracted_data)
        
        # Calculate completeness and readiness
        completeness = self._calculate_completeness(merged_profile)
        extracted_fields = self._build_extracted_fields(merged_profile)
        is_ready = self._check_readiness_for_current_self_gen(merged_profile)
        
        return ExtractionResult(
            session_id=ctx.session_id,
            extracted_profile=merged_profile,
            profile_completeness=completeness,
            extracted_fields=extracted_fields,
            is_ready_for_current_self_gen=is_ready,
        )

    def _build_extraction_prompt(self, ctx: ExtractionContext) -> str:
        """Build extraction prompt from interview transcript."""
        # Reconstruct conversation for context
        transcript_text = "\n".join(
            f"{line['role'].upper()}: {line['content']}"
            for line in ctx.transcript_history[-20:]  # last 20 turns for context
        )
        
        existing_profile = (
            f"\n\nPreviously extracted profile:\n{ctx.current_profile.model_dump_json(indent=2)}"
            if ctx.current_profile
            else ""
        )
        
        return f"""\
As a profile extraction specialist, analyze the interview transcript below and extract/refine the user's profile across six life dimensions.

INTERVIEW TRANSCRIPT:
{transcript_text}
{existing_profile}

Guidelines:
1. Merge new information with existing data (don't overwrite unless explicitly contradicted)
2. Rate confidence 0-1 for each section (0=not mentioned, 1=explicitly stated and detailed)
3. Surface contradictions in hidden_tensions
4. Only mark dilemma_confidence >= 0.8 when the user has explicitly named the core decision
5. Preserve any data that remains relevant from previous extractions

Return a complete profile extraction in JSON format with all fields populated (use empty values if not mentioned).
"""

    def _merge_profiles(
        self, 
        existing: UserProfile | None, 
        extracted: RawExtractedProfileData
    ) -> UserProfile:
        """
        Merge extracted profile with existing profile.
        Prefers extracted data where confidence is high, preserves existing otherwise.
        """
        if not existing:
            # First extraction: create new profile
            return UserProfile(
                id=extracted.psychology.get("user_id", ""),  # Will be set by router
                core_values=extracted.psychology.get("core_values", []),
                fears=extracted.psychology.get("fears", []),
                hidden_tensions=extracted.psychology.get("hidden_tensions", []),
                decision_style=extracted.decision_style,
                self_narrative=extracted.self_narrative,
                current_dilemma=extracted.current_dilemma,
                career=CareerProfile(**extracted.career),
                financial=FinancialProfile(**extracted.financial),
                personal=PersonalProfile(**extracted.personal),
                health=HealthProfile(**extracted.health),
                life_situation=LifeSituationProfile(**extracted.life_situation),
            )
        
        # Merge: prefer high-confidence new data, preserve existing otherwise
        def merge_field(existing_val: Any, new_val: Any, confidence: float) -> Any:
            if confidence >= 0.7 and new_val:
                return new_val
            return existing_val or new_val
        
        def merge_list(existing: list, new: list, confidence: float) -> list:
            if confidence >= 0.7 and new:
                # Merge deduplicated
                combined = set(existing + new)
                return list(combined)
            return existing or new
        
        # Merge each profile section
        merged = UserProfile(
            id=existing.id,
            core_values=merge_list(
                existing.core_values,
                extracted.psychology.get("core_values", []),
                extracted.psychology_confidence,
            ),
            fears=merge_list(
                existing.fears,
                extracted.psychology.get("fears", []),
                extracted.psychology_confidence,
            ),
            hidden_tensions=merge_list(
                existing.hidden_tensions,
                extracted.psychology.get("hidden_tensions", []),
                extracted.psychology_confidence,
            ),
            decision_style=merge_field(
                existing.decision_style,
                extracted.decision_style,
                extracted.decision_style_confidence,
            ),
            self_narrative=merge_field(
                existing.self_narrative,
                extracted.self_narrative,
                extracted.self_narrative_confidence,
            ),
            current_dilemma=merge_field(
                existing.current_dilemma,
                extracted.current_dilemma,
                extracted.dilemma_confidence,
            ),
            career=CareerProfile(**{
                **existing.career.model_dump(),
                **{k: v for k, v in extracted.career.items() if v},
            }),
            financial=FinancialProfile(**{
                **existing.financial.model_dump(),
                **{k: v for k, v in extracted.financial.items() if v},
            }),
            personal=PersonalProfile(**{
                **existing.personal.model_dump(),
                **{k: v for k, v in extracted.personal.items() if v},
            }),
            health=HealthProfile(**{
                **existing.health.model_dump(),
                **{k: v for k, v in extracted.health.items() if v},
            }),
            life_situation=LifeSituationProfile(**{
                **existing.life_situation.model_dump(),
                **{k: v for k, v in extracted.life_situation.items() if v},
            }),
        )
        
        return merged

    def _calculate_completeness(self, profile: UserProfile) -> float:
        """Calculate profile completeness as 0-1 score."""
        total_fields = 25  # Approximate count of extractable fields
        filled_fields = 0
        
        # Core required fields
        if profile.core_values:
            filled_fields += 1
        if profile.fears:
            filled_fields += 1
        if profile.hidden_tensions:
            filled_fields += 1
        if profile.decision_style:
            filled_fields += 1
        if profile.self_narrative:
            filled_fields += 1
        if profile.current_dilemma:
            filled_fields += 1
        
        # Career
        if profile.career.job_title:
            filled_fields += 1
        if profile.career.industry:
            filled_fields += 1
        if profile.career.career_goal:
            filled_fields += 1
        
        # Financial
        if profile.financial.income_level:
            filled_fields += 1
        if profile.financial.money_mindset:
            filled_fields += 1
        
        # Personal
        if profile.personal.relationships:
            filled_fields += 1
        if profile.personal.hobbies:
            filled_fields += 1
        if profile.personal.personal_values:
            filled_fields += 1
        
        # Health
        if profile.health.physical_health:
            filled_fields += 1
        if profile.health.mental_health:
            filled_fields += 1
        
        # Life situation
        if profile.life_situation.current_location:
            filled_fields += 1
        if profile.life_situation.life_stage:
            filled_fields += 1
        
        return min(1.0, filled_fields / total_fields)

    def _build_extracted_fields(self, profile: UserProfile) -> dict[str, bool]:
        """Build extracted_fields dict for UI feedback."""
        return {
            "core_values": bool(profile.core_values),
            "fears": bool(profile.fears),
            "hidden_tensions": bool(profile.hidden_tensions),
            "decision_style": bool(profile.decision_style),
            "self_narrative": bool(profile.self_narrative),
            "current_dilemma": bool(profile.current_dilemma),
            "job_title": bool(profile.career.job_title),
            "industry": bool(profile.career.industry),
            "career_goal": bool(profile.career.career_goal),
            "income_level": bool(profile.financial.income_level),
            "money_mindset": bool(profile.financial.money_mindset),
            "relationships": bool(profile.personal.relationships),
            "hobbies": bool(profile.personal.hobbies),
            "personal_values": bool(profile.personal.personal_values),
            "physical_health": bool(profile.health.physical_health),
            "mental_health": bool(profile.health.mental_health),
            "current_location": bool(profile.life_situation.current_location),
            "life_stage": bool(profile.life_situation.life_stage),
        }

    def _check_readiness_for_current_self_gen(self, profile: UserProfile) -> bool:
        """
        Check if profile has enough data to auto-generate CurrentSelf.
        
        Requires:
        - Dilemma confidence >= 0.8 (explicit statement)
        - Core values defined
        - Decision style defined
        - Fears/tensions defined
        - Self narrative or reasonable inference
        """
        has_dilemma = bool(profile.current_dilemma) and len(profile.current_dilemma) > 10
        has_psychology = bool(profile.core_values and profile.fears)
        has_narrative = bool(profile.self_narrative) or (
            profile.decision_style and profile.hidden_tensions
        )
        
        return has_dilemma and has_psychology and has_narrative # type: ignore
