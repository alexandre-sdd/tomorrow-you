#!/usr/bin/env python3
"""
Interactive Pipeline Test Runner

Semi-automated test that allows manual inputs for realistic pipeline testing.
Provides guided flow through all stages with options to:
- Use auto-generated test data or provide custom inputs
- Skip stages or repeat them
- See intermediate results and tree visualization
- Suitable for demos and manual validation

Usage:
    python backend/test_pipeline_interactive.py
    python backend/test_pipeline_interactive.py --auto-mode
    python backend/test_pipeline_interactive.py --session-id <existing>
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
    ContextResolver,
    MistralChatClient,
    MistralChatConfig,
    PromptComposer,
    PromptComposerConfig,
    append_conversation_turn,
)
from backend.engines.prompt_composer import ChatMessage
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
# Display Utilities
# ---------------------------------------------------------------------------

def print_header(text: str) -> None:
    """Print section header."""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}\n")


def print_stage(stage_num: int, title: str) -> None:
    """Print stage header."""
    print(f"\n{'=' * 70}")
    print(f"STAGE {stage_num}: {title}")
    print(f"{'=' * 70}\n")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"✓ {text}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"✗ {text}")


def print_future_selves(future_selves: list[SelfCard]) -> None:
    """Display future selves with details."""
    for i, self_card in enumerate(future_selves, 1):
        print(f"\n  {i}. {self_card.name} (Depth {self_card.depth_level})")
        print(f"     🎯 Goal: {self_card.optimization_goal}")
        print(f"     💭 Belief: {self_card.core_belief}")
        print(f"     ⚖️  Trade-off: {self_card.trade_off}")
        if self_card.parent_self_id:
            print(f"     👤 Parent: {self_card.parent_self_id[:12]}...")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for yes/no answer."""
    default_str = "Y/n" if default else "y/N"
    response = input(f"{question} ({default_str})> ").strip().lower()
    
    if not response:
        return default
    
    return response in ("y", "yes")


def create_default_profile() -> UserProfile:
    """Create default test profile for quick starts."""
    return UserProfile(
        id=f"profile_{uuid.uuid4().hex[:8]}",
        core_values=["Growth", "Creativity", "Security"],
        fears=["Stagnation", "Missed opportunities", "Financial risk"],
        hidden_tensions=["Comfort vs ambition", "Stability vs creativity"],
        decision_style="Analytical but bold when committed",
        self_narrative="Professional at crossroads seeking meaningful direction",
        current_dilemma="Should I pursue my passion or maintain career stability?",
        career=CareerProfile(
            job_title="Senior Software Engineer",
            industry="Technology",
            seniority_level="senior",
            years_experience=8,
            current_company="TechCorp",
            career_goal="Find work that aligns with values and passions",
            job_satisfaction="6/10",
            main_challenges=["Feeling unchallenged", "Lack of passion", "Golden handcuffs"],
        ),
        financial=FinancialProfile(
            income_level="150k+",
            financial_goals=["Build safety net", "Invest in self"],
            money_mindset="Security-focused but willing to invest strategically",
            risk_tolerance="medium",
            main_financial_concern="Income loss during transition",
        ),
        personal=PersonalProfile(
            hobbies=["Baking", "Reading", "Hiking"],
            daily_routines=["Morning coffee ritual", "Evening walks"],
            main_interests=["Culinary arts", "Entrepreneurship", "Technology"],
            relationships="In partnership",
            key_relationships=["Partner (supportive)", "Close friends"],
            personal_values=["Authenticity", "Growth", "Connection"],
        ),
        health=HealthProfile(
            physical_health="Good - active lifestyle",
            mental_health="Moderate stress from work dissatisfaction",
            health_goals=["Reduce stress", "More creative outlets"],
        ),
        life_situation=LifeSituationProfile(
            current_location="San Francisco",
            life_stage="Early-mid career",
            major_responsibilities=["Maintaining household stability"],
            recent_transitions=["Re-evaluating long-term career direction"],
            upcoming_changes=["Possible move into entrepreneurship"],
        ),
    )


# ---------------------------------------------------------------------------
# Interactive Stages
# ---------------------------------------------------------------------------

async def interactive_stage_1(
    session_id: str,
    orchestrator: PipelineOrchestrator,
    auto_mode: bool,
) -> None:
    """Interactive Stage 1: Onboarding."""
    print_stage(1, "ONBOARDING & CURRENT SELF GENERATION")
    
    # Check existing session
    try:
        session_data = orchestrator._load_session(session_id)
        
        if session_data.get("currentSelf"):
            print_info("Session already has CurrentSelf!")
            if not prompt_yes_no("Skip onboarding and continue?"):
                sys.exit(0)
            return
        
        if session_data.get("userProfile"):
            print_info("Found existing profile.")
            profile = UserProfile(**session_data["userProfile"])
        else:
            profile = None
    
    except Exception:
        profile = None
    
    # Get or create profile
    if not profile:
        if auto_mode or prompt_yes_no("Use default test profile?"):
            profile = create_default_profile()
            print_info("Using default test profile")
        else:
            print("\nPlease run interview first:")
            print(f"  python backend/test_onboarding_live.py --mode interactive --session-id {session_id}")
            sys.exit(0)
        
        # Save profile
        session_dir = Path(orchestrator.storage_root) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        session_data = {
            "id": session_id,
            "username": "Interactive Test User",
            "status": "onboarding",
            "userProfile": profile.model_dump(mode="json"),
            "createdAt": time.time(),
            "updatedAt": time.time(),
        }
        
        session_file = session_dir / "session.json"
        session_file.write_text(json.dumps(session_data, indent=2))
    
    # Show profile summary
    print(f"\n📋 Profile Summary:")
    print(f"   Dilemma: {profile.current_dilemma}")
    print(f"   Core Values: {', '.join(profile.core_values[:3])}")
    print(f"   Career: {profile.career.job_title}")
    
    if not auto_mode and not prompt_yes_no("\nGenerate CurrentSelf from this profile?"):
        sys.exit(0)
    
    # Generate CurrentSelf
    try:
        print("\n⏳ Generating CurrentSelf...")
        profile_out, current_self = await orchestrator.complete_onboarding_flow(
            session_id=session_id
        )
        
        print(f"\n✨ Generated CurrentSelf: {current_self.name}")
        print(f"   🎯 Goal: {current_self.optimization_goal}")
        print(f"   💭 Belief: {current_self.core_belief}")
        print(f"   🎨 Mood: {current_self.visual_style.mood}")
        
        print_info("\n✅ Stage 1 Complete: CurrentSelf created")
    
    except Exception as exc:
        print_error(f"Failed to generate CurrentSelf: {exc}")
        sys.exit(1)


async def interactive_stage_2(
    session_id: str,
    orchestrator: PipelineOrchestrator,
    visualizer: TreeVisualizer,
    auto_mode: bool,
) -> list[SelfCard]:
    """Interactive Stage 2: Root future generation."""
    print_stage(2, "ROOT FUTURE SELF GENERATION")
    
    session_data = orchestrator._load_session(session_id)
    
    # Check if already generated
    if session_data.get("futureSelvesFull"):
        print_info("Future selves already generated!")
        
        future_selves = [SelfCard(**data) for data in session_data["futureSelvesFull"].values()]
        root_futures = [fs for fs in future_selves if fs.depth_level == 1]
        
        print_future_selves(root_futures)
        
        if not auto_mode and not prompt_yes_no("\nContinue with existing futures?"):
            sys.exit(0)
        
        return root_futures
    
    # Get number of futures
    if auto_mode:
        num_futures = 3
    else:
        try:
            num_str = input("\nHow many future selves to generate? [2-5, default 3]> ").strip()
            num_futures = int(num_str) if num_str else 3
            num_futures = max(2, min(5, num_futures))
        except ValueError:
            num_futures = 3
    
    # Generate
    try:
        print(f"\n⏳ Generating {num_futures} root-level future selves...")
        future_selves = await orchestrator.initialize_exploration(
            session_id=session_id,
            num_futures=num_futures,
        )
        
        print(f"\n✨ Generated {len(future_selves)} future selves:")
        print_future_selves(future_selves)
        
        print_info("\n✅ Stage 2 Complete: Future selves generated")
        
        return future_selves
    
    except Exception as exc:
        print_error(f"Failed to generate future selves: {exc}")
        sys.exit(1)


async def interactive_stage_3(
    session_id: str,
    future_selves: list[SelfCard],
    orchestrator: PipelineOrchestrator,
    auto_mode: bool,
) -> tuple[SelfCard, int]:
    """Interactive Stage 3: Conversation."""
    print_stage(3, "CONVERSATION WITH FUTURE SELF")
    
    # Select future self
    if auto_mode:
        selected_idx = 0
    else:
        while True:
            choice = input(f"\nSelect future self to talk with [1-{len(future_selves)}]> ").strip()
            try:
                selected_idx = int(choice) - 1
                if 0 <= selected_idx < len(future_selves):
                    break
                print_error(f"Please enter 1-{len(future_selves)}")
            except ValueError:
                print_error("Please enter a valid number")
    
    target_self = future_selves[selected_idx]
    
    print(f"\n💬 Starting conversation with: {target_self.name}")
    print(f"   Goal: {target_self.optimization_goal}\n")
    
    # Set up conversation
    settings = get_settings()
    resolver = ContextResolver(storage_root=settings.storage_root)
    
    try:
        branch_name = resolver.find_branch_for_self(session_id, target_self.id)
        context = resolver.resolve(session_id, branch_name)
    except Exception as exc:
        print_error(f"Failed to resolve context: {exc}")
        sys.exit(1)
    
    chat_client = MistralChatClient(
        api_key=settings.mistral_api_key,
        config=MistralChatConfig(
            model=settings.mistral_model,
            temperature=0.7,
            max_tokens=300,
        )
    )
    
    composer = PromptComposer(config=PromptComposerConfig())
    
    # Conversation loop
    history: list[ChatMessage] = []
    turn_count = 0
    
    if auto_mode:
        # Auto conversation
        auto_messages = [
            "Tell me about your typical day.",
            "What was the hardest decision you made?",
            "What advice would you give me?",
        ]
        
        for msg in auto_messages:
            print(f"\nYou: {msg}")
            
            messages = composer.compose_messages(context, msg, history)
            response = chat_client.chat(messages)
            
            print(f"{target_self.name}: {response}\n")
            
            history.append({"role": "user", "content": msg})
            history.append({"role": "assistant", "content": response})
            turn_count += 1
            
            # Persist
            append_conversation_turn(
                session_id=session_id,
                storage_root=settings.storage_root,
                user_text=msg,
                assistant_text=response,
                self_id=target_self.id,
                self_name=target_self.name,
                branch_name=branch_name,
            )
            
            await asyncio.sleep(0.5)
    
    else:
        # Interactive conversation
        print("Type your messages (or 'done' to finish conversation):\n")
        
        while True:
            user_msg = input("You> ").strip()
            
            if not user_msg:
                continue
            
            if user_msg.lower() == "done":
                break
            
            try:
                messages = composer.compose_messages(context, user_msg, history)
                response = chat_client.chat(messages)
                
                print(f"{target_self.name}> {response}\n")
                
                history.append({"role": "user", "content": user_msg})
                history.append({"role": "assistant", "content": response})
                turn_count += 1
                
                # Persist
                append_conversation_turn(
                    session_id=session_id,
                    storage_root=settings.storage_root,
                    user_text=user_msg,
                    assistant_text=response,
                    self_id=target_self.id,
                    self_name=target_self.name,
                    branch_name=branch_name,
                )
            
            except Exception as exc:
                print_error(f"Error: {exc}")
                break
    
    print_info(f"\n✅ Stage 3 Complete: {turn_count} conversation turns")
    
    return target_self, turn_count


async def interactive_stage_4(
    session_id: str,
    parent_self: SelfCard,
    orchestrator: PipelineOrchestrator,
    visualizer: TreeVisualizer,
    auto_mode: bool,
) -> list[SelfCard] | None:
    """Interactive Stage 4: Secondary branching."""
    print_stage(4, "DEEPER EXPLORATION (BRANCHING)")
    
    if not auto_mode:
        if not prompt_yes_no(f"\nGenerate deeper futures from {parent_self.name}?"):
            return None
    
    try:
        print(f"\n⏳ Generating secondary future selves from {parent_self.name}...")
        child_selves = await orchestrator.branch_from_conversation(
            session_id=session_id,
            parent_self_id=parent_self.id,
            num_futures=3,
        )
        
        print(f"\n✨ Generated {len(child_selves)} secondary future selves:")
        print_future_selves(child_selves)
        
        # Show tree
        print("\n🌳 Updated Exploration Tree:")
        print(visualizer.render_tree(session_id, parent_self.id))
        
        print_info("\n✅ Stage 4 Complete: Secondary futures generated")
        
        return child_selves
    
    except Exception as exc:
        print_error(f"Failed to generate secondary futures: {exc}")
        return None


async def interactive_stage_5(
    session_id: str,
    visualizer: TreeVisualizer,
) -> None:
    """Interactive Stage 5: Tree navigation & stats."""
    print_stage(5, "TREE NAVIGATION & STATISTICS")
    
    # Show tree
    print("\n🌳 Full Exploration Tree:")
    print(visualizer.render_tree(session_id))
    
    # Show statistics
    stats = visualizer.get_branch_statistics(session_id)
    print("\n📊 Statistics:")
    print(f"   Total Future Selves: {stats['total_selves']}")
    print(f"   Maximum Depth: {stats['max_depth']}")
    print(f"   Branches with Conversations: {stats['branches_with_conversations']}")
    print(f"   Total Conversation Turns: {stats['total_conversation_turns']}")
    
    if stats['depth_distribution']:
        print(f"\n   Depth Distribution:")
        for depth, count in sorted(stats['depth_distribution'].items()):
            print(f"     Level {depth}: {count} selves")
    
    # Show available branches
    branches = visualizer.list_available_branches(session_id)
    print(f"\n📋 All Available Branches ({len(branches)}):")
    for branch in branches:
        conv_indicator = f"({branch['conversation_turns']} turns)" if branch['conversation_turns'] > 0 else "(no conversation)"
        print(f"   • {branch['name']} - Depth {branch['depth_level']} {conv_indicator}")
    
    print_info("\n✅ Stage 5 Complete: Tree validated")


# ---------------------------------------------------------------------------
# Main Runner
# ---------------------------------------------------------------------------

async def run_interactive_test(session_id: str | None, auto_mode: bool) -> int:
    """Run interactive pipeline test."""
    print_header("INTERACTIVE PIPELINE TEST")
    
    settings = get_settings()
    
    # Create or use session
    if not session_id:
        session_id = f"interactive_{int(time.time())}"
        print_info(f"Created new session: {session_id}")
    else:
        print_info(f"Using session: {session_id}")
    
    orchestrator = PipelineOrchestrator(storage_root=settings.storage_root)
    visualizer = TreeVisualizer(storage_root=settings.storage_root)
    
    try:
        # Stage 1: Onboarding
        await interactive_stage_1(session_id, orchestrator, auto_mode)
        
        if not auto_mode and not prompt_yes_no("\nContinue to Stage 2?"):
            return 0
        
        # Stage 2: Root generation
        future_selves = await interactive_stage_2(
            session_id, orchestrator, visualizer, auto_mode
        )
        
        if not auto_mode and not prompt_yes_no("\nContinue to Stage 3?"):
            return 0
        
        # Stage 3: Conversation
        target_self, turn_count = await interactive_stage_3(
            session_id, future_selves, orchestrator, auto_mode
        )
        
        if not auto_mode and not prompt_yes_no("\nContinue to Stage 4?"):
            # Show final tree and exit
            await interactive_stage_5(session_id, visualizer)
            return 0
        
        # Stage 4: Secondary branching
        child_selves = await interactive_stage_4(
            session_id, target_self, orchestrator, visualizer, auto_mode
        )
        
        # Stage 5: Tree navigation
        await interactive_stage_5(session_id, visualizer)
        
        # Final summary
        print_header("TEST COMPLETE")
        print(f"Session ID: {session_id}")
        print(f"Location: {Path(settings.storage_root) / session_id}")
        print("\nYou can continue exploring this session with:")
        print(f"  python backend/cli/full_pipeline_demo.py --session-id {session_id}")
        
        return 0
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 1
    except Exception as exc:
        print_error(f"\nFatal error: {exc}")
        import traceback
        traceback.print_exc()
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Interactive pipeline test with manual/auto modes"
    )
    parser.add_argument(
        "--session-id",
        help="Use existing session (creates new if not provided)"
    )
    parser.add_argument(
        "--auto-mode",
        action="store_true",
        help="Run in automatic mode with minimal prompts"
    )
    
    args = parser.parse_args()
    
    return asyncio.run(run_interactive_test(
        session_id=args.session_id,
        auto_mode=args.auto_mode,
    ))


if __name__ == "__main__":
    sys.exit(main())
