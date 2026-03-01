"""
Pipeline Router

HTTP endpoints for orchestrating complete workflows:
- Complete onboarding → CurrentSelf generation
- Initialize exploration → Root future self generation
- Branch from conversation → Deeper future self generation
- Get pipeline status → Current state and available actions

These endpoints wrap PipelineOrchestrator methods with proper HTTP semantics.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.config.settings import Settings, get_settings
from backend.engines.pipeline_orchestrator import (
    InvalidStateError,
    PipelineOrchestrator,
    PipelineOrchestratorError,
)
from backend.models.schemas import SelfCard, UserProfile

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

def _camel_config() -> ConfigDict:
    return ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CompleteOnboardingRequest(BaseModel):
    model_config = _camel_config()

    session_id: str
    user_confirmed_dilemma: str | None = Field(
        default=None,
        description="Optional user-confirmed dilemma to override extracted value"
    )


class CompleteOnboardingResponse(BaseModel):
    model_config = _camel_config()

    session_id: str
    user_profile: UserProfile
    current_self: SelfCard
    message: str = "Onboarding complete! Ready to explore future selves."


class InitializeExplorationRequest(BaseModel):
    model_config = _camel_config()

    session_id: str
    num_futures: int = Field(
        default=3,
        ge=2,
        le=5,
        description="Number of root-level future selves to generate (2-5)"
    )


class InitializeExplorationResponse(BaseModel):
    model_config = _camel_config()

    session_id: str
    future_selves: list[SelfCard]
    message: str = "Root-level future selves generated. Choose one to explore."


class BranchFromConversationRequest(BaseModel):
    model_config = _camel_config()

    session_id: str
    parent_self_id: str = Field(description="ID of parent self to branch from")
    num_futures: int = Field(
        default=3,
        ge=2,
        le=5,
        description="Number of child future selves to generate (2-5)"
    )


class BranchFromConversationResponse(BaseModel):
    model_config = _camel_config()

    session_id: str
    parent_self_id: str
    parent_self_name: str
    child_selves: list[SelfCard]
    message: str


class PipelineStatusResponse(BaseModel):
    model_config = _camel_config()

    session_id: str
    phase: str
    status: str | None
    available_actions: list[str]
    current_self: dict | None
    future_selves_count: int
    exploration_depth: int
    conversation_branches: list[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/complete-onboarding", response_model=CompleteOnboardingResponse)
async def complete_onboarding(
    request: CompleteOnboardingRequest,
    settings: Settings = Depends(get_settings),
) -> CompleteOnboardingResponse:
    """
    Complete onboarding and generate CurrentSelf.

    Validates profile completeness, generates CurrentSelf persona card,
    and transitions session to ready_for_future_self_generation state.

    Requirements:
    - Profile must be at least 50% complete
    - CurrentSelf not already generated

    Returns CurrentSelf and updated UserProfile.
    """
    orchestrator = PipelineOrchestrator(storage_root=settings.storage_root)

    try:
        profile, current_self = await orchestrator.complete_onboarding_flow(
            session_id=request.session_id,
            user_confirmed_dilemma=request.user_confirmed_dilemma,
        )
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PipelineOrchestratorError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return CompleteOnboardingResponse(
        session_id=request.session_id,
        user_profile=profile,
        current_self=current_self,
    )


@router.post("/start-exploration", response_model=InitializeExplorationResponse)
async def start_exploration(
    request: InitializeExplorationRequest,
    settings: Settings = Depends(get_settings),
) -> InitializeExplorationResponse:
    """
    Generate root-level future selves and initialize memory tree.

    Creates 2-5 contrasting future selves from CurrentSelf and UserProfile,
    sets up memory branch structure, and transitions to selection phase.

    Requirements:
    - CurrentSelf must exist (onboarding complete)
    - Future selves not already generated

    Use /conversation/reply to start conversing with a chosen future self.
    """
    orchestrator = PipelineOrchestrator(storage_root=settings.storage_root)

    try:
        future_selves = await orchestrator.initialize_exploration(
            session_id=request.session_id,
            num_futures=request.num_futures,
        )
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PipelineOrchestratorError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return InitializeExplorationResponse(
        session_id=request.session_id,
        future_selves=future_selves,
    )


@router.post("/branch-conversation", response_model=BranchFromConversationResponse)
async def branch_conversation(
    request: BranchFromConversationRequest,
    settings: Settings = Depends(get_settings),
) -> BranchFromConversationResponse:
    """
    Generate deeper future selves from conversation context.

    Analyzes transcript for insights, resolves ancestor context,
    and generates secondary/tertiary future selves based on
    conversation with parent self.

    Requirements:
    - Parent self must exist
    - At least one conversation exchange with parent self

    Creates child branches that inherit context from parent path.
    """
    orchestrator = PipelineOrchestrator(storage_root=settings.storage_root)

    try:
        child_selves = await orchestrator.branch_from_conversation(
            session_id=request.session_id,
            parent_self_id=request.parent_self_id,
            num_futures=request.num_futures,
        )
    except InvalidStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PipelineOrchestratorError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    # Get parent self name from session
    session_data = orchestrator._load_session(request.session_id)
    future_selves_full = session_data.get("futureSelvesFull", {})
    parent_self = SelfCard(**future_selves_full[request.parent_self_id])

    return BranchFromConversationResponse(
        session_id=request.session_id,
        parent_self_id=request.parent_self_id,
        parent_self_name=parent_self.name,
        child_selves=child_selves,
        message=f"Generated {len(child_selves)} future selves from {parent_self.name}",
    )


@router.get("/status/{session_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> PipelineStatusResponse:
    """
    Get current pipeline state and available actions.

    Returns:
    - phase: Current phase (onboarding/selection/conversation)
    - status: Session status
    - available_actions: Valid next actions (complete_onboarding, initialize_exploration, etc.)
    - current_self: CurrentSelf if exists
    - future_selves_count: Number of generated future selves
    - exploration_depth: Maximum depth of exploration tree
    - conversation_branches: Selves with conversation history (candidates for branching)

    Use this to determine which pipeline endpoints are available.
    """
    orchestrator = PipelineOrchestrator(storage_root=settings.storage_root)

    try:
        status_data = orchestrator.get_pipeline_status(session_id)
    except PipelineOrchestratorError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PipelineStatusResponse(**status_data)
