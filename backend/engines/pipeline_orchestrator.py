"""
Pipeline Orchestrator

Coordinates multi-step flows in the Tomorrow You system:
- Onboarding completion → CurrentSelf generation
- Root future self generation with memory initialization
- Conversation-driven branching with transcript analysis

Provides high-level orchestration methods that chain individual engines
while maintaining state consistency and proper error handling.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from backend.config.settings import get_settings
from backend.engines.current_self_auto_generator import (
    CurrentSelfAutoGeneratorEngine,
    CurrentSelfGenerationContext,
)
from backend.models.schemas import GenerateFutureSelvesRequest, SelfCard, UserProfile
from backend.routers.future_self import generate_future_selves


class PipelineOrchestratorError(Exception):
    """Base exception for pipeline orchestration errors."""
    pass


class InvalidStateError(PipelineOrchestratorError):
    """Raised when pipeline operation is attempted in invalid state."""
    pass


class PipelineOrchestrator:
    """Orchestrates multi-step workflows across engines."""

    def __init__(self, storage_root: str | None = None):
        self.storage_root = storage_root or get_settings().storage_root

    # ---------------------------------------------------------------------------
    # Storage helpers
    # ---------------------------------------------------------------------------

    def _get_session_path(self, session_id: str) -> Path:
        """Get path to session.json file."""
        return Path(self.storage_root) / session_id / "session.json"

    def _load_session(self, session_id: str) -> dict[str, Any]:
        """Load session from disk."""
        path = self._get_session_path(session_id)
        if not path.exists():
            raise PipelineOrchestratorError(f"Session {session_id} not found")
        with open(path) as f:
            return json.load(f)

    def _save_session(self, session_id: str, session_data: dict[str, Any]) -> None:
        """Save session to disk, updating timestamp."""
        session_data["updatedAt"] = time.time()
        path = self._get_session_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(session_data, f, indent=2)

    def _initialize_memory_tree(self, session_id: str, current_self: SelfCard) -> None:
        """
        Initialize memory tree structure with root node.
        
        Creates memory/nodes/ directory and root node with currentSelf.
        This is called when onboarding completes.
        """
        session_dir = Path(self.storage_root) / session_id
        nodes_dir = session_dir / "memory" / "nodes"
        nodes_dir.mkdir(parents=True, exist_ok=True)
        
        # Create root node with currentSelf
        now = time.time()
        root_node_id = "root_node"
        
        root_node = {
            "id": root_node_id,
            "parentId": None,  # Root has no parent
            "branchLabel": "root",
            "facts": [
                {
                    "id": f"fact_{root_node_id}_0",
                    "fact": f"Current self: {current_self.name}",
                    "source": "onboarding",
                    "extractedAt": now,
                },
                {
                    "id": f"fact_{root_node_id}_1",
                    "fact": f"Optimization goal: {current_self.optimization_goal}",
                    "source": "onboarding",
                    "extractedAt": now,
                }
            ],
            "notes": ["Root node created during onboarding"],
            "selfCard": current_self.model_dump(by_alias=True),
            "createdAt": now,
        }
        
        # Write root node
        root_node_file = nodes_dir / f"{root_node_id}.json"
        root_node_file.write_text(json.dumps(root_node, indent=2), encoding="utf-8")
        
        # Initialize branches.json with root branch
        branches_file = session_dir / "memory" / "branches.json"
        branches = [
            {
                "name": "root",
                "headNodeId": root_node_id,
                "parentBranchName": None,
            }
        ]
        branches_file.write_text(json.dumps(branches, indent=2), encoding="utf-8")

    def _get_transcript_path(self, session_id: str) -> Path:
        """Get path to transcript.json file."""
        return Path(self.storage_root) / session_id / "transcript.json"

    def _load_transcript(self, session_id: str) -> list[dict[str, Any]]:
        """Load transcript from disk."""
        path = self._get_transcript_path(session_id)
        if not path.exists():
            return []
        with open(path) as f:
            return json.load(f)

    def _calculate_completeness(self, profile: UserProfile) -> float:
        """Calculate profile completeness as 0-1."""
        total_fields = 20
        filled_fields = 0

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
        if profile.career.job_title:
            filled_fields += 1
        if profile.career.career_goal:
            filled_fields += 1
        if profile.financial.income_level:
            filled_fields += 1
        if profile.financial.money_mindset:
            filled_fields += 1
        if profile.personal.relationships:
            filled_fields += 1
        if profile.personal.hobbies:
            filled_fields += 1
        if profile.personal.personal_values:
            filled_fields += 1
        if profile.health.mental_health:
            filled_fields += 1
        if profile.health.physical_health:
            filled_fields += 1
        if profile.life_situation.current_location:
            filled_fields += 1
        if profile.life_situation.life_stage:
            filled_fields += 1

        return min(1.0, filled_fields / total_fields)

    # ---------------------------------------------------------------------------
    # Orchestration methods
    # ---------------------------------------------------------------------------

    async def complete_onboarding_flow(
        self,
        session_id: str,
        user_confirmed_dilemma: str | None = None,
    ) -> tuple[UserProfile, SelfCard]:
        """
        Complete onboarding and generate CurrentSelf.

        Validates profile completeness, optionally updates dilemma,
        generates CurrentSelf, and transitions to ready state.

        Args:
            session_id: Session identifier
            user_confirmed_dilemma: Optional user-confirmed dilemma override

        Returns:
            Tuple of (UserProfile, CurrentSelf SelfCard)

        Raises:
            InvalidStateError: If profile incomplete or CurrentSelf already exists
            PipelineOrchestratorError: If generation fails
        """
        session_data = self._load_session(session_id)

        # Validate state
        if session_data.get("currentSelf"):
            raise InvalidStateError(
                f"Session {session_id} already has CurrentSelf. Cannot re-run onboarding."
            )

        # Load and validate profile
        profile_dict = session_data.get("userProfile", {})
        if not profile_dict:
            raise InvalidStateError(
                f"Session {session_id} has no user profile. Complete interview first."
            )

        profile = UserProfile(**profile_dict)
        completeness = self._calculate_completeness(profile)

        if completeness < 0.5:
            raise InvalidStateError(
                f"Profile completeness is {completeness:.1%}. "
                "Must be at least 50% to complete onboarding."
            )

        # Update dilemma if provided
        if user_confirmed_dilemma:
            profile.current_dilemma = user_confirmed_dilemma

        # Generate CurrentSelf
        current_self_gen = CurrentSelfAutoGeneratorEngine()
        gen_ctx = CurrentSelfGenerationContext(
            session_id=session_id,
            user_profile=profile,
        )

        try:
            gen_result = await current_self_gen.generate(gen_ctx)
            current_self = gen_result.current_self
        except Exception as exc:
            raise PipelineOrchestratorError(
                f"CurrentSelf generation failed: {str(exc)}"
            ) from exc

        # Save to session
        session_data["userProfile"] = profile.model_dump(mode="json")
        session_data["currentSelf"] = current_self.model_dump(mode="json")
        session_data["status"] = "ready_for_future_self_generation"
        
        # Initialize memory tree structure with root node
        self._initialize_memory_tree(session_id, current_self)
        
        self._save_session(session_id, session_data)

        return profile, current_self

    async def initialize_exploration(
        self,
        session_id: str,
        num_futures: int = 3,
    ) -> list[SelfCard]:
        """
        Generate root-level future selves and initialize memory tree.

        Creates 2-3 contrasting future selves from CurrentSelf and UserProfile,
        sets up memory branches, and transitions to selection phase.

        Args:
            session_id: Session identifier
            num_futures: Number of future selves to generate (2-3 recommended)

        Returns:
            List of generated root-level SelfCards

        Raises:
            InvalidStateError: If CurrentSelf not present or futures already generated
            PipelineOrchestratorError: If generation fails
        """
        session_data = self._load_session(session_id)
        if not session_data.get("currentSelf"):
            raise InvalidStateError(
                f"Session {session_id} has no CurrentSelf. Complete onboarding first."
            )
        if session_data.get("futureSelvesFull"):
            raise InvalidStateError(
                f"Session {session_id} already has future selves. Use branch_from_conversation for deeper exploration."
            )

        try:
            response = await generate_future_selves(
                request=GenerateFutureSelvesRequest(
                    session_id=session_id,
                    count=max(2, min(3, num_futures)),
                    parent_self_id=None,
                ),
                settings=get_settings(),
            )
            return response.future_self_options
        except Exception as exc:
            raise PipelineOrchestratorError(
                f"Root future self generation failed: {str(exc)}"
            ) from exc

    async def branch_from_conversation(
        self,
        session_id: str,
        parent_self_id: str,
        num_futures: int = 3,
    ) -> list[SelfCard]:
        """
        Generate deeper future selves from conversation context.

        Analyzes transcript for insights, resolves ancestor context,
        and generates secondary/tertiary future selves based on
        conversation with parent self.

        Args:
            session_id: Session identifier
            parent_self_id: ID of parent self to branch from
            num_futures: Number of future selves to generate

        Returns:
            List of generated child SelfCards

        Raises:
            InvalidStateError: If parent self not found or no conversation history
            PipelineOrchestratorError: If generation fails
        """
        session_data = self._load_session(session_id)
        future_selves_full = session_data.get("futureSelvesFull", {})
        if parent_self_id not in future_selves_full:
            raise InvalidStateError(
                f"Parent self {parent_self_id} not found in session {session_id}"
            )

        transcript = self._load_transcript(session_id)
        has_conversation = any(
            t.get("phase") == "conversation" and t.get("selfId") == parent_self_id
            for t in transcript
        )
        if not has_conversation:
            raise InvalidStateError(
                f"No conversation history with parent self {parent_self_id}. "
                "Have a conversation before branching."
            )

        try:
            response = await generate_future_selves(
                request=GenerateFutureSelvesRequest(
                    session_id=session_id,
                    count=max(2, min(3, num_futures)),
                    parent_self_id=parent_self_id,
                ),
                settings=get_settings(),
            )
            return response.future_self_options
        except Exception as exc:
            raise PipelineOrchestratorError(
                f"Child future self generation failed: {str(exc)}"
            ) from exc

    def get_pipeline_status(self, session_id: str) -> dict[str, Any]:
        """
        Get current pipeline state and available actions.

        Returns dict with:
        - phase: Current phase (onboarding/selection/conversation/branching)
        - status: Session status
        - available_actions: List of valid next actions
        - current_self: CurrentSelf if exists
        - future_selves_count: Number of generated future selves
        - conversation_branches: Selves with conversation history
        """
        session_data = self._load_session(session_id)

        phase = session_data.get("status", "onboarding")
        current_self = session_data.get("currentSelf")
        future_selves_full = session_data.get("futureSelvesFull", {})
        transcript = self._load_transcript(session_id)

        # Determine available actions
        available_actions = []
        selves_with_conversation: set[str] = set()

        if not current_self:
            available_actions.append("complete_onboarding")
        elif not future_selves_full:
            available_actions.append("initialize_exploration")
        else:
            available_actions.append("start_conversation")
            
            # Check which selves have conversation history
            for entry in transcript:
                if entry.get("phase") == "conversation" and entry.get("selfId"):
                    selves_with_conversation.add(entry["selfId"])

            if selves_with_conversation:
                available_actions.append("branch_from_conversation")

        # Get selves with conversation for branching opportunities
        conversation_branches = []
        for self_id in selves_with_conversation:
            if self_id in future_selves_full:
                self_card = SelfCard(**future_selves_full[self_id])
                conversation_branches.append({
                    "self_id": self_id,
                    "name": self_card.name,
                    "depth": self_card.depth_level,
                })

        return {
            "session_id": session_id,
            "phase": phase,
            "status": session_data.get("status"),
            "available_actions": available_actions,
            "current_self": current_self,
            "future_selves_count": len(future_selves_full),
            "exploration_depth": max(
                (SelfCard(**s).depth_level for s in future_selves_full.values()),
                default=0
            ),
            "conversation_branches": conversation_branches,
        }
