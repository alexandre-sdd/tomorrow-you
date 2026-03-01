#!/usr/bin/env python3
"""
Full Pipeline End-to-End Test

Automated test that validates the complete Tomorrow You workflow:
1. Onboarding completion → CurrentSelf generation
2. Root future self generation → Memory tree initialization
3. Conversation with future self → Transcript persistence
4. Secondary branching → Deeper future generation with context
5. Tree navigation → Verification of tree structure

Simulates user interactions with scripted inputs to ensure
all components work together correctly.

Usage:
    python backend/test_full_pipeline_e2e.py
    python backend/test_full_pipeline_e2e.py --keep-session
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

# Add backend to path for standalone execution
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config.settings import get_settings
from backend.engines.pipeline_orchestrator import (
    InvalidStateError,
    PipelineOrchestrator,
    PipelineOrchestratorError,
)
from backend.engines.tree_visualizer import TreeVisualizer
from backend.engines import (
    BranchConversationSession,
    ContextResolver,
    MistralChatClient,
    MistralChatConfig,
    PromptComposer,
    PromptComposerConfig,
    append_conversation_turn,
)
from backend.engines.prompt_composer import ChatMessage
from backend.engines.current_self_auto_generator import (
    CurrentSelfAutoGeneratorEngine,
    CurrentSelfGenerationContext,
)
from backend.models.schemas import (
    SelfCard,
    UserProfile,
    CareerProfile,
    FinancialProfile,
    PersonalProfile,
    HealthProfile,
    LifeSituationProfile,
)

# Load .env if available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Test Utilities
# ---------------------------------------------------------------------------

class TestResult:
    """Container for test results."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []
    
    def assert_true(self, condition: bool, message: str) -> None:
        """Assert condition is True."""
        if condition:
            self.passed += 1
            print(f"  ✅ {message}")
        else:
            self.failed += 1
            self.errors.append(message)
            print(f"  ❌ FAIL: {message}")
    
    def assert_equals(self, actual: Any, expected: Any, message: str) -> None:
        """Assert actual equals expected."""
        if actual == expected:
            self.passed += 1
            print(f"  ✅ {message}")
        else:
            self.failed += 1
            error_msg = f"{message} (expected: {expected}, got: {actual})"
            self.errors.append(error_msg)
            print(f"  ❌ FAIL: {error_msg}")
    
    def assert_not_none(self, value: Any, message: str) -> None:
        """Assert value is not None."""
        self.assert_true(value is not None, message)
    
    def assert_greater(self, actual: Any, threshold: Any, message: str) -> None:
        """Assert actual > threshold."""
        self.assert_true(actual > threshold, f"{message} ({actual} > {threshold})")
    
    def print_summary(self) -> None:
        """Print test summary."""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Total: {self.passed + self.failed}")
        
        if self.errors:
            print("\nFailed Assertions:")
            for error in self.errors:
                print(f"  - {error}")
        
        print("=" * 70 + "\n")


def print_stage(stage_num: int, title: str) -> None:
    """Print stage header."""
    print(f"\n{'=' * 70}")
    print(f"STAGE {stage_num}: {title}")
    print(f"{'=' * 70}\n")


def create_test_profile() -> UserProfile:
    """Create a complete test user profile."""
    return UserProfile(
        id=f"profile_{uuid.uuid4().hex[:8]}",
        core_values=[
            "Personal growth",
            "Creative expression",
            "Financial security",
        ],
        fears=[
            "Stagnation",
            "Missing opportunities",
            "Financial instability",
        ],
        hidden_tensions=[
            "Comfort vs ambition",
            "Stability vs creativity",
        ],
        decision_style="Analytical but impulsive once decided",
        self_narrative="Software engineer considering career pivot to creative field",
        current_dilemma="Should I keep my stable tech job or pursue my passion for baking?",
        career=CareerProfile(
            job_title="Senior Software Engineer",
            industry="Technology",
            seniority_level="senior",
            years_experience=8,
            current_company="TechCorp",
            career_goal="Find more meaningful work that combines creativity and stability",
            job_satisfaction="6/10",
            main_challenges=[
                "Feeling unchallenged",
                "Lack of creative outlet",
                "Golden handcuffs",
            ],
        ),
        financial=FinancialProfile(
            income_level="150k+",
            financial_goals=[
                "Build emergency fund",
                "Save for business",
            ],
            money_mindset="Security-focused but willing to invest in self",
            risk_tolerance="medium",
            main_financial_concern="Loss of steady income if career pivot fails",
        ),
        personal=PersonalProfile(
            hobbies=["Baking", "Reading", "Hiking"],
            daily_routines=["Morning coffee", "Evening walk"],
            main_interests=["Culinary arts", "Small business", "Technology"],
            relationships="In partnership",
            key_relationships=["Partner (supportive)", "Parents (traditional)", "Close friend group"],
            personal_values=["Authenticity", "Growth", "Connection"],
        ),
        health=HealthProfile(
            physical_health="Good - active lifestyle",
            mental_health="Moderate stress from work dissatisfaction",
            health_goals=["Reduce work stress", "More creative outlets"],
        ),
        life_situation=LifeSituationProfile(
            current_location="San Francisco",
            life_stage="Early-mid career, no children",
            major_responsibilities=["Career transition planning", "Shared household planning"],
            recent_transitions=["Exploring entrepreneurship seriously"],
            upcoming_changes=["Potential shift away from full-time tech"],
        ),
    )


# ---------------------------------------------------------------------------
# Test Stages
# ---------------------------------------------------------------------------

async def stage_1_onboarding(
    session_id: str,
    orchestrator: PipelineOrchestrator,
    result: TestResult,
) -> None:
    """Stage 1: Complete onboarding and generate CurrentSelf."""
    print_stage(1, "ONBOARDING → CURRENT SELF GENERATION")
    
    # Create test profile
    profile = create_test_profile()
    
    # Save initial session with profile
    session_dir = Path(orchestrator.storage_root) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    
    session_data = {
        "id": session_id,
        "username": "E2E Test User",
        "status": "onboarding",
        "userProfile": profile.model_dump(mode="json"),
        "createdAt": time.time(),
        "updatedAt": time.time(),
    }
    
    session_file = session_dir / "session.json"
    session_file.write_text(json.dumps(session_data, indent=2))
    
    print("📝 Created test session with complete profile")
    
    # Complete onboarding
    try:
        profile_out, current_self = await orchestrator.complete_onboarding_flow(
            session_id=session_id
        )
        
        print(f"\n✅ Generated CurrentSelf: {current_self.name}")
        print(f"   Goal: {current_self.optimization_goal}")
        print(f"   Belief: {current_self.core_belief}\n")
        
        # Assertions
        result.assert_not_none(current_self, "CurrentSelf generated")
        result.assert_equals(current_self.type, "current", "CurrentSelf type is 'current'")
        result.assert_equals(current_self.depth_level, 0, "CurrentSelf depth is 0")
        result.assert_not_none(current_self.name, "CurrentSelf has name")
        result.assert_not_none(current_self.optimization_goal, "CurrentSelf has optimization goal")
        result.assert_not_none(current_self.core_belief, "CurrentSelf has core belief")
        
        # Verify session status
        session_data = orchestrator._load_session(session_id)
        result.assert_equals(
            session_data.get("status"),
            "ready_for_future_self_generation",
            "Session status updated correctly"
        )
        
    except Exception as exc:
        result.assert_true(False, f"Onboarding completion failed: {exc}")
        raise


async def stage_2_root_generation(
    session_id: str,
    orchestrator: PipelineOrchestrator,
    visualizer: TreeVisualizer,
    result: TestResult,
) -> list[SelfCard]:
    """Stage 2: Generate root-level future selves."""
    print_stage(2, "ROOT FUTURE SELF GENERATION")
    
    try:
        future_selves = await orchestrator.initialize_exploration(
            session_id=session_id,
            num_futures=3,
        )
        
        print(f"\n✅ Generated {len(future_selves)} root-level future selves:\n")
        for i, self_card in enumerate(future_selves, 1):
            print(f"  {i}. {self_card.name} (depth {self_card.depth_level})")
            print(f"     Goal: {self_card.optimization_goal}")
        print()
        
        # Assertions
        result.assert_equals(len(future_selves), 3, "Generated 3 future selves")
        
        for self_card in future_selves:
            result.assert_equals(self_card.type, "future", f"{self_card.name} type is 'future'")
            result.assert_equals(self_card.depth_level, 1, f"{self_card.name} depth is 1")
            result.assert_equals(
                self_card.parent_self_id,
                None,
                f"{self_card.name} parent_self_id is None (root level)"
            )
            result.assert_not_none(self_card.name, f"{self_card.name} has name")
            result.assert_not_none(self_card.optimization_goal, f"{self_card.name} has goal")
        
        # Verify session data structures
        session_data = orchestrator._load_session(session_id)
        result.assert_equals(
            len(session_data.get("futureSelvesFull", {})),
            3,
            "futureSelvesFull contains 3 selves"
        )
        result.assert_equals(
            len(session_data.get("futureSelfOptions", [])),
            3,
            "futureSelfOptions contains 3 selves"
        )
        result.assert_true(
            "root" in session_data.get("explorationPaths", {}),
            "explorationPaths has root entry"
        )
        result.assert_equals(
            len(session_data.get("explorationPaths", {}).get("root", [])),
            3,
            "Root exploration path has 3 children"
        )
        
        # Verify memory structures
        memory_dir = Path(orchestrator.storage_root) / session_id / "memory"
        nodes_dir = memory_dir / "nodes"
        branches_file = memory_dir / "branches.json"
        
        result.assert_true(nodes_dir.exists(), "Memory nodes directory exists")
        result.assert_true(branches_file.exists(), "branches.json exists")
        
        # Should have 4 nodes: 1 root + 3 futures
        node_files = list(nodes_dir.glob("*.json"))
        result.assert_equals(len(node_files), 4, "Memory tree has 4 nodes (1 root + 3 futures)")
        
        # Verify transcript
        transcript = orchestrator._load_transcript(session_id)
        selection_entries = [e for e in transcript if e.get("phase") == "selection"]
        result.assert_greater(len(selection_entries), 0, "Transcript has selection phase entries")
        
        return future_selves
    
    except Exception as exc:
        result.assert_true(False, f"Root generation failed: {exc}")
        raise


async def stage_3_conversation(
    session_id: str,
    target_self: SelfCard,
    orchestrator: PipelineOrchestrator,
    result: TestResult,
) -> list[tuple[str, str]]:
    """Stage 3: Have conversation with selected future self."""
    print_stage(3, f"CONVERSATION WITH {target_self.name.upper()}")
    
    settings = get_settings()
    resolver = ContextResolver(storage_root=settings.storage_root)
    
    try:
        branch_name = resolver.find_branch_for_self(session_id, target_self.id)
        context = resolver.resolve(session_id, branch_name)
        
        print(f"💬 Starting conversation with {target_self.name}\n")
        
        chat_client = MistralChatClient(
            api_key=settings.mistral_api_key,
            config=MistralChatConfig(
                model=settings.mistral_model,
                temperature=0.7,
                top_p=0.95,
                max_tokens=300,
            )
        )
        
        composer = PromptComposer(config=PromptComposerConfig())
        
        # Simulated conversation
        conversation_exchanges = [
            "Hi! Tell me about your typical day.",
            "What was the hardest part about making this career change?",
            "How do you balance creativity with financial stability?",
            "What advice would you give to me right now?",
        ]
        
        history: list[ChatMessage] = []
        conversation_log: list[tuple[str, str]] = []
        
        for i, user_msg in enumerate(conversation_exchanges, 1):
            print(f"[Turn {i}]")
            print(f"User: {user_msg}")
            
            messages = composer.compose_messages(context, user_msg, history)
            response = chat_client.chat(messages)
            
            print(f"{target_self.name}: {response[:100]}{'...' if len(response) > 100 else ''}\n")
            
            history.append({"role": "user", "content": user_msg})
            history.append({"role": "assistant", "content": response})
            conversation_log.append((user_msg, response))
            
            # Persist to transcript
            append_conversation_turn(
                session_id=session_id,
                storage_root=settings.storage_root,
                user_text=user_msg,
                assistant_text=response,
                self_id=target_self.id,
                self_name=target_self.name,
                branch_name=branch_name,
            )
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)
        
        print(f"✅ Completed {len(conversation_exchanges)} conversation turns\n")
        
        # Assertions
        result.assert_equals(
            len(conversation_log),
            len(conversation_exchanges),
            f"Completed all {len(conversation_exchanges)} exchanges"
        )
        
        # Verify transcript persistence
        transcript = orchestrator._load_transcript(session_id)
        conversation_entries = [
            e for e in transcript
            if e.get("phase") == "conversation" and e.get("selfId") == target_self.id
        ]
        
        # Should have 2x exchanges (user + assistant)
        expected_entries = len(conversation_exchanges) * 2
        result.assert_greater(
            len(conversation_entries),
            0,
            "Transcript has conversation entries"
        )
        print(f"  📝 Transcript has {len(conversation_entries)} conversation entries")
        
        return conversation_log
    
    except Exception as exc:
        result.assert_true(False, f"Conversation failed: {exc}")
        raise


async def stage_4_secondary_branching(
    session_id: str,
    parent_self: SelfCard,
    orchestrator: PipelineOrchestrator,
    visualizer: TreeVisualizer,
    result: TestResult,
) -> list[SelfCard]:
    """Stage 4: Generate secondary future selves from conversation."""
    print_stage(4, "SECONDARY BRANCHING")
    
    print(f"🌿 Generating deeper futures from {parent_self.name}...\n")
    
    try:
        child_selves = await orchestrator.branch_from_conversation(
            session_id=session_id,
            parent_self_id=parent_self.id,
            num_futures=3,
        )
        
        print(f"\n✅ Generated {len(child_selves)} secondary future selves:\n")
        for i, self_card in enumerate(child_selves, 1):
            print(f"  {i}. {self_card.name} (depth {self_card.depth_level})")
            print(f"     Parent: {parent_self.name}")
            print(f"     Goal: {self_card.optimization_goal}")
        print()
        
        # Assertions
        result.assert_equals(len(child_selves), 3, "Generated 3 child selves")
        
        for self_card in child_selves:
            result.assert_equals(
                self_card.type,
                "future",
                f"{self_card.name} type is 'future'"
            )
            result.assert_equals(
                self_card.depth_level,
                2,
                f"{self_card.name} depth is 2 (parent + 1)"
            )
            result.assert_equals(
                self_card.parent_self_id,
                parent_self.id,
                f"{self_card.name} parent_self_id matches parent"
            )
        
        # Verify parent updated with children
        session_data = orchestrator._load_session(session_id)
        parent_data = session_data["futureSelvesFull"][parent_self.id]
        parent_children = parent_data.get("childrenIds", [])
        
        result.assert_equals(
            len(parent_children),
            3,
            "Parent self has 3 children_ids"
        )
        
        # Verify exploration paths updated
        result.assert_true(
            parent_self.id in session_data.get("explorationPaths", {}),
            "explorationPaths has parent entry"
        )
        
        # Verify memory nodes created
        nodes_dir = Path(orchestrator.storage_root) / session_id / "memory" / "nodes"
        node_files = list(nodes_dir.glob("*.json"))
        result.assert_equals(
            len(node_files),
            7,
            "Memory tree has 7 nodes (1 root + 3 level-1 + 3 level-2)"
        )
        
        return child_selves
    
    except Exception as exc:
        result.assert_true(False, f"Secondary branching failed: {exc}")
        raise


async def stage_5_tree_navigation(
    session_id: str,
    visualizer: TreeVisualizer,
    parent_self: SelfCard,
    result: TestResult,
) -> None:
    """Stage 5: Verify tree structure and navigation."""
    print_stage(5, "TREE NAVIGATION & VERIFICATION")
    
    try:
        # Get statistics
        stats = visualizer.get_branch_statistics(session_id)
        
        print("📊 Tree Statistics:\n")
        print(f"  Total Future Selves: {stats['total_selves']}")
        print(f"  Maximum Depth: {stats['max_depth']}")
        print(f"  Branches with Conversations: {stats['branches_with_conversations']}")
        print(f"  Total Conversation Turns: {stats['total_conversation_turns']}")
        print(f"\n  Depth Distribution:")
        for depth, count in sorted(stats['depth_distribution'].items()):
            print(f"    Depth {depth}: {count} selves")
        print()
        
        # Assertions
        result.assert_equals(stats['total_selves'], 6, "Total of 6 future selves")
        result.assert_equals(stats['max_depth'], 2, "Maximum depth is 2")
        result.assert_greater(
            stats['branches_with_conversations'],
            0,
            "At least one branch has conversation"
        )
        result.assert_greater(
            stats['total_conversation_turns'],
            0,
            "Total conversation turns > 0"
        )
        
        # Test tree rendering
        tree_str = visualizer.render_tree(session_id, parent_self.id)
        result.assert_true(len(tree_str) > 0, "Tree renders successfully")
        result.assert_true("EXPLORATION TREE" in tree_str, "Tree contains header")
        result.assert_true(parent_self.name in tree_str, "Tree contains parent self")
        
        print("🌳 Tree Structure:\n")
        print(tree_str)
        print()
        
        # Test navigation functions
        branches = visualizer.list_available_branches(session_id)
        result.assert_equals(len(branches), 6, "list_available_branches returns 6 branches")
        
        # Test ancestor retrieval
        session_data_raw = json.loads(
            (Path(visualizer.storage_root) / session_id / "session.json").read_text()
        )
        child_ids = session_data_raw["futureSelvesFull"][parent_self.id].get("childrenIds", [])
        
        if child_ids:
            first_child_id = child_ids[0]
            ancestors = visualizer.get_ancestors(session_id, first_child_id)
            result.assert_equals(len(ancestors), 1, "Child has 1 ancestor (parent)")
            result.assert_equals(
                ancestors[0]["self_id"],
                parent_self.id,
                "Ancestor is parent self"
            )
        
        # Test sibling retrieval
        if len(child_ids) >= 2:
            siblings = visualizer.get_siblings(session_id, child_ids[0])
            result.assert_equals(
                len(siblings),
                2,
                "First child has 2 siblings"
            )
        
    except Exception as exc:
        result.assert_true(False, f"Tree navigation failed: {exc}")
        raise


# ---------------------------------------------------------------------------
# Main Test Runner
# ---------------------------------------------------------------------------

async def run_full_pipeline_test(keep_session: bool = False) -> int:
    """Run complete E2E test."""
    print("\n" + "=" * 70)
    print("TOMORROW YOU - FULL PIPELINE E2E TEST")
    print("=" * 70 + "\n")
    
    settings = get_settings()
    session_id = f"e2e_{uuid.uuid4().hex[:8]}"
    
    print(f"🔬 Test Session: {session_id}\n")
    
    orchestrator = PipelineOrchestrator(storage_root=settings.storage_root)
    visualizer = TreeVisualizer(storage_root=settings.storage_root)
    result = TestResult()
    
    try:
        # Stage 1: Onboarding
        await stage_1_onboarding(session_id, orchestrator, result)
        
        # Stage 2: Root generation
        future_selves = await stage_2_root_generation(
            session_id, orchestrator, visualizer, result
        )
        
        # Stage 3: Conversation (with first future self)
        target_self = future_selves[0]
        await stage_3_conversation(session_id, target_self, orchestrator, result)
        
        # Stage 4: Secondary branching
        child_selves = await stage_4_secondary_branching(
            session_id, target_self, orchestrator, visualizer, result
        )
        
        # Stage 5: Tree navigation
        await stage_5_tree_navigation(session_id, visualizer, target_self, result)
        
        # Print results
        result.print_summary()
        
        # Cleanup
        if not keep_session:
            import shutil
            session_dir = Path(settings.storage_root) / session_id
            if session_dir.exists():
                shutil.rmtree(session_dir)
                print(f"🧹 Cleaned up test session: {session_id}\n")
        else:
            print(f"💾 Kept test session: {session_id}\n")
        
        return 0 if result.failed == 0 else 1
    
    except Exception as exc:
        print(f"\n❌ FATAL ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Full pipeline E2E test - validates complete workflow"
    )
    parser.add_argument(
        "--keep-session",
        action="store_true",
        help="Keep test session after completion (don't clean up)"
    )
    
    args = parser.parse_args()
    
    return asyncio.run(run_full_pipeline_test(keep_session=args.keep_session))


if __name__ == "__main__":
    sys.exit(main())
