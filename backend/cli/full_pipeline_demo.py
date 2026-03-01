#!/usr/bin/env python3
"""
Full Pipeline Demo CLI

Interactive demonstration of the complete Tomorrow You pipeline:
1. Onboarding → Profile extraction → CurrentSelf generation
2. Root future self generation
3. Conversation with selected future self
4. Multi-level branching from conversation
5. Tree navigation (/tree, /back, /switch commands)

Usage:
    python backend/cli/full_pipeline_demo.py
    python backend/cli/full_pipeline_demo.py --session-id <existing_session>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Literal

# Add backend to path for standalone execution
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
from backend.models.schemas import SelfCard, UserProfile

# Load .env if available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
except ImportError:
    pass


# ---------------------------------------------------------------------------
# State Machine Types
# ---------------------------------------------------------------------------

PipelinePhase = Literal["onboarding", "selection", "conversation", "branching"]


class DemoState:
    """State container for demo session."""

    def __init__(self, session_id: str, storage_root: str):
        self.session_id = session_id
        self.storage_root = storage_root
        self.phase: PipelinePhase = "onboarding"
        
        # Conversation state
        self.current_self_id: str | None = None
        self.conversation_history: list[ChatMessage] = []
        
        # Navigation state
        self.navigation_stack: list[str] = []  # Stack of self_ids for /back command
        
        # Orchestrator and visualizer
        self.orchestrator = PipelineOrchestrator(storage_root=storage_root)
        self.visualizer = TreeVisualizer(storage_root=storage_root)

    def load_session_data(self) -> dict:
        """Load current session data."""
        session_path = Path(self.storage_root) / self.session_id / "session.json"
        if not session_path.exists():
            raise Exception(f"Session {self.session_id} not found")
        return json.loads(session_path.read_text())


# ---------------------------------------------------------------------------
# Display Helpers
# ---------------------------------------------------------------------------

def print_header(text: str) -> None:
    """Print section header."""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}\n")


def print_separator() -> None:
    """Print section separator."""
    print("-" * 70)


def print_error(text: str) -> None:
    """Print error message."""
    print(f"\n❌ ERROR: {text}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"\n✅ {text}\n")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"ℹ️  {text}")


def print_future_selves(future_selves: list[SelfCard]) -> None:
    """Display generated future selves."""
    print("\n📋 Generated Future Selves:\n")
    for i, self_card in enumerate(future_selves, 1):
        print(f"  {i}. {self_card.name}")
        print(f"     Goal: {self_card.optimization_goal}")
        print(f"     Belief: {self_card.core_belief}")
        print(f"     Trade-off: {self_card.trade_off}")
        print(f"     Depth: {self_card.depth_level}")
        print()


# ---------------------------------------------------------------------------
# Phase Handlers
# ---------------------------------------------------------------------------

async def handle_onboarding_phase(state: DemoState) -> None:
    """Handle onboarding phase - simulated for demo."""
    print_header("PHASE 1: ONBOARDING")
    
    print("In a real implementation, this would run the full interview flow.")
    print("For this demo, we'll simulate a completed profile.\n")
    
    # Check if session exists and has profile
    try:
        session_data = state.load_session_data()
        if session_data.get("currentSelf"):
            print_info("Session already has CurrentSelf. Skipping onboarding.")
            state.phase = "selection"
            return
        
        if session_data.get("userProfile"):
            print_info("Profile exists. Generating CurrentSelf...")
        else:
            print_error("No profile found. Please run interview first using:")
            print("  python backend/test_onboarding_live.py --mode interactive")
            sys.exit(1)
    except Exception:
        print_error("Session not found. Please create a session first using:")
        print("  python backend/test_onboarding_live.py --mode interactive")
        sys.exit(1)
    
    # Complete onboarding
    try:
        profile, current_self = await state.orchestrator.complete_onboarding_flow(
            session_id=state.session_id
        )
        
        print_success("Onboarding complete!")
        print(f"CurrentSelf: {current_self.name}")
        print(f"Optimization Goal: {current_self.optimization_goal}")
        print(f"Core Belief: {current_self.core_belief}\n")
        
        state.phase = "selection"
        
    except InvalidStateError as exc:
        if "already has CurrentSelf" in str(exc):
            print_info("CurrentSelf already exists. Moving to selection.")
            state.phase = "selection"
        else:
            print_error(str(exc))
            sys.exit(1)
    except PipelineOrchestratorError as exc:
        print_error(f"Failed to complete onboarding: {exc}")
        sys.exit(1)


async def handle_selection_phase(state: DemoState) -> None:
    """Handle selection phase - generate and select future self."""
    print_header("PHASE 2: FUTURE SELF SELECTION")
    
    session_data = state.load_session_data()
    
    # Check if futures already generated
    future_selves_full = session_data.get("futureSelvesFull", {})
    
    if not future_selves_full:
        print("Generating root-level future selves...\n")
        
        try:
            future_selves = await state.orchestrator.initialize_exploration(
                session_id=state.session_id,
                num_futures=3,
            )
            
            print_success("Future selves generated!")
            print_future_selves(future_selves)
            
        except (InvalidStateError, PipelineOrchestratorError) as exc:
            print_error(f"Failed to generate future selves: {exc}")
            sys.exit(1)
    else:
        print_info("Future selves already generated.")
        
        # Load and display existing futures
        future_selves = [SelfCard(**data) for data in future_selves_full.values()]
        root_futures = [fs for fs in future_selves if fs.depth_level == 1]
        
        if root_futures:
            print_future_selves(root_futures)
    
    # Let user select a future self
    print_separator()
    print("Enter the number of the future self you'd like to explore:")
    print("(Or type 'tree' to see the full exploration tree)\n")
    
    while True:
        choice = input("Choice> ").strip()
        
        if choice.lower() == "tree":
            print(state.visualizer.render_tree(state.session_id))
            continue
        
        try:
            idx = int(choice) - 1
            session_data = state.load_session_data()
            future_selves_full = session_data.get("futureSelvesFull", {})
            root_futures = [
                SelfCard(**data) for data in future_selves_full.values()
                if SelfCard(**data).depth_level == 1
            ]
            
            if 0 <= idx < len(root_futures):
                selected_self = root_futures[idx]
                state.current_self_id = selected_self.id
                state.conversation_history = []
                state.navigation_stack = []
                state.phase = "conversation"
                
                print_success(f"Selected: {selected_self.name}")
                print(f"Let's talk with your {selected_self.name} self.\n")
                break
            else:
                print_error(f"Please enter a number between 1 and {len(root_futures)}")
        except ValueError:
            print_error("Please enter a valid number or 'tree'")


async def handle_conversation_phase(state: DemoState) -> None:
    """Handle conversation phase - chat with future self."""
    if not state.current_self_id:
        print_error("No future self selected")
        return
    
    # Load self info
    session_data = state.load_session_data()
    future_selves_full = session_data.get("futureSelvesFull", {})
    
    if state.current_self_id not in future_selves_full:
        print_error(f"Future self {state.current_self_id} not found")
        return
    
    current_self = SelfCard(**future_selves_full[state.current_self_id])
    
    print_header(f"PHASE 3: CONVERSATION WITH {current_self.name.upper()}")
    
    print(f"💬 Chatting with: {current_self.name}")
    print(f"   Depth: {current_self.depth_level}")
    print(f"   Goal: {current_self.optimization_goal}\n")
    
    print("Commands:")
    print("  /branch  - Generate deeper future selves from this conversation")
    print("  /back    - Go back to parent self")
    print("  /switch  - Switch to a different future self")
    print("  /tree    - View exploration tree")
    print("  /stats   - View conversation statistics")
    print("  /exit    - Exit conversation\n")
    print_separator()
    
    # Set up conversation components
    settings = get_settings()
    resolver = ContextResolver(storage_root=settings.storage_root)
    
    try:
        branch_name = resolver.find_branch_for_self(state.session_id, state.current_self_id)
        context = resolver.resolve(state.session_id, branch_name)
    except Exception as exc:
        print_error(f"Failed to resolve context: {exc}")
        return
    
    chat_client = MistralChatClient(
        api_key=settings.mistral_api_key,
        config=MistralChatConfig(
            model=settings.mistral_model,
            temperature=0.7,
            top_p=0.95,
            max_tokens=500,
        )
    )
    
    composer = PromptComposer(config=PromptComposerConfig())
    
    # Conversation loop
    while True:
        user_input = input(f"\nYou> ").strip()
        
        if not user_input:
            continue
        
        # Handle commands
        if user_input.startswith("/"):
            command = user_input.lower()
            
            if command == "/exit":
                print_info("Exiting conversation...")
                break
            
            elif command == "/branch":
                state.phase = "branching"
                break
            
            elif command == "/back":
                active_self_id = state.current_self_id
                if not active_self_id:
                    print_error("No active self to navigate from")
                    continue
                ancestors = state.visualizer.get_ancestors(state.session_id, active_self_id)
                if ancestors:
                    parent = ancestors[-1]
                    state.navigation_stack.append(active_self_id)
                    state.current_self_id = parent["self_id"]
                    state.conversation_history = []
                    print_success(f"Navigated back to: {parent['name']}")
                    # Restart conversation phase with new self
                    await handle_conversation_phase(state)
                    return
                else:
                    print_info("Already at root level. Use /switch to choose a different self.")
            
            elif command == "/switch":
                branches = state.visualizer.list_available_branches(state.session_id)
                print("\n📋 Available Branches:\n")
                for i, branch in enumerate(branches, 1):
                    marker = "→" if branch["self_id"] == state.current_self_id else " "
                    print(f"  {i}. {marker} {branch['name']} (depth {branch['depth_level']}, {branch['conversation_turns']} turns)")
                print()
                
                switch_choice = input("Enter number to switch to (or press Enter to cancel)> ").strip()
                if switch_choice:
                    try:
                        idx = int(switch_choice) - 1
                        if 0 <= idx < len(branches):
                            new_self_id = branches[idx]["self_id"]
                            if state.current_self_id:
                                state.navigation_stack.append(state.current_self_id)
                            state.current_self_id = new_self_id
                            state.conversation_history = []
                            print_success(f"Switched to: {branches[idx]['name']}")
                            # Restart conversation phase with new self
                            await handle_conversation_phase(state)
                            return
                    except ValueError:
                        print_error("Invalid choice")
            
            elif command == "/tree":
                print(state.visualizer.render_tree(state.session_id, state.current_self_id))
            
            elif command == "/stats":
                stats = state.visualizer.get_branch_statistics(state.session_id)
                print("\n📊 Statistics:\n")
                print(f"  Total Future Selves: {stats['total_selves']}")
                print(f"  Maximum Depth: {stats['max_depth']}")
                print(f"  Current Conversation Turns: {len(state.conversation_history) // 2}")
                print()
            
            else:
                print_error(f"Unknown command: {command}")
            
            continue
        
        # Send message to future self
        try:
            messages = composer.compose_messages(context, user_input, state.conversation_history)
            response = chat_client.chat(messages)
            
            if not response:
                print_error("Received empty response")
                continue
            
            print(f"\n{current_self.name}> {response}\n")
            
            # Update history
            state.conversation_history.append({"role": "user", "content": user_input})
            state.conversation_history.append({"role": "assistant", "content": response})
            
            # Persist to transcript (best-effort)
            try:
                append_conversation_turn(
                    session_id=state.session_id,
                    storage_root=settings.storage_root,
                    user_text=user_input,
                    assistant_text=response,
                    self_id=state.current_self_id,
                    self_name=current_self.name,
                    branch_name=branch_name,
                )
            except Exception as exc:
                print(f"Warning: Failed to persist transcript: {exc}")
        
        except Exception as exc:
            print_error(f"Conversation error: {exc}")


async def handle_branching_phase(state: DemoState) -> None:
    """Handle branching phase - generate deeper futures."""
    if not state.current_self_id:
        print_error("No current self selected")
        return
    
    print_header("PHASE 4: DEEPER EXPLORATION")
    
    session_data = state.load_session_data()
    future_selves_full = session_data.get("futureSelvesFull", {})
    current_self = SelfCard(**future_selves_full[state.current_self_id])
    
    print(f"Generating deeper future selves from {current_self.name}...\n")
    print_info("Analyzing conversation transcripts for insights...")
    
    try:
        child_selves = await state.orchestrator.branch_from_conversation(
            session_id=state.session_id,
            parent_self_id=state.current_self_id,
            num_futures=3,
        )
        
        print_success(f"Generated {len(child_selves)} future selves!")
        print_future_selves(child_selves)
        
        # Ask if user wants to explore one
        print_separator()
        print("Would you like to explore one of these selves? (y/n)")
        choice = input("> ").strip().lower()
        
        if choice == "y":
            print("\nEnter the number of the future self to explore:")
            while True:
                try:
                    idx = int(input("Choice> ").strip()) - 1
                    if 0 <= idx < len(child_selves):
                        selected = child_selves[idx]
                        state.navigation_stack.append(state.current_self_id)
                        state.current_self_id = selected.id
                        state.conversation_history = []
                        state.phase = "conversation"
                        
                        print_success(f"Selected: {selected.name}")
                        await handle_conversation_phase(state)
                        return
                    else:
                        print_error(f"Please enter 1-{len(child_selves)}")
                except ValueError:
                    print_error("Please enter a valid number")
        else:
            # Return to conversation with parent
            state.phase = "conversation"
            print_info(f"Returning to conversation with {current_self.name}")
            await handle_conversation_phase(state)
    
    except (InvalidStateError, PipelineOrchestratorError) as exc:
        print_error(f"Branching failed: {exc}")
        state.phase = "conversation"


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

async def run_demo(session_id: str | None = None) -> None:
    """Run the full pipeline demo."""
    settings = get_settings()
    
    # Create or load session
    if not session_id:
        session_id = f"demo_{int(time.time())}"
        session_dir = Path(settings.storage_root) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize empty session
        session_data = {
            "id": session_id,
            "username": "Demo User",
            "status": "onboarding",
            "createdAt": time.time(),
            "updatedAt": time.time(),
        }
        session_file = session_dir / "session.json"
        session_file.write_text(json.dumps(session_data, indent=2))
        
        print_info(f"Created new session: {session_id}")
        print_info("Please run onboarding first:")
        print(f"  python backend/test_onboarding_live.py --mode interactive --session-id {session_id}\n")
        sys.exit(0)
    
    state = DemoState(session_id=session_id, storage_root=settings.storage_root)
    
    # Determine starting phase
    try:
        status_data = state.orchestrator.get_pipeline_status(session_id)
        
        if not status_data["current_self"]:
            state.phase = "onboarding"
        elif status_data["future_selves_count"] == 0:
            state.phase = "selection"
        else:
            state.phase = "selection"
        
        print_header("TOMORROW YOU - FULL PIPELINE DEMO")
        print(f"Session: {session_id}")
        print(f"Phase: {status_data['phase']}")
        print(f"Future Selves: {status_data['future_selves_count']}")
        print(f"Max Depth: {status_data['exploration_depth']}")
        
    except Exception as exc:
        print_error(f"Failed to load session: {exc}")
        sys.exit(1)
    
    # Run pipeline phases
    while True:
        try:
            if state.phase == "onboarding":
                await handle_onboarding_phase(state)
            
            elif state.phase == "selection":
                await handle_selection_phase(state)
            
            elif state.phase == "conversation":
                await handle_conversation_phase(state)
            
            elif state.phase == "branching":
                await handle_branching_phase(state)
            
            else:
                print_error(f"Unknown phase: {state.phase}")
                break
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as exc:
            print_error(f"Unexpected error: {exc}")
            import traceback
            traceback.print_exc()
            break
    
    # Show final tree
    print_header("FINAL EXPLORATION TREE")
    try:
        print(state.visualizer.render_tree(state.session_id, state.current_self_id))
    except Exception as exc:
        print(f"Could not render tree: {exc}")
    
    print_info("Demo complete!")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Full pipeline demo - onboarding through branching navigation"
    )
    parser.add_argument(
        "--session-id",
        help="Existing session ID (creates new if not provided)",
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_demo(session_id=args.session_id))
        return 0
    except Exception as exc:
        print_error(f"Fatal error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
