from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load .env from repository root (works when launched from root or backend/)
try:
    from dotenv import load_dotenv

    _repo_root = Path(__file__).resolve().parents[1]
    _env_path = _repo_root / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path, override=False)
        os.environ.setdefault("ENV_FILE_LOADED", str(_env_path))
except Exception:
    pass

from fastapi.testclient import TestClient

from backend.app import app


def _print_json(title: str, payload: dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _start(client: TestClient, session_id: str, user_name: str) -> dict[str, Any]:
    resp = client.post(
        "/interview/start",
        json={"session_id": session_id, "user_name": user_name},
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"/interview/start failed ({resp.status_code}): {resp.text}")
    return resp.json()


def _reply(client: TestClient, session_id: str, message: str) -> dict[str, Any]:
    resp = client.post(
        "/interview/reply",
        json={"session_id": session_id, "user_message": message},
        timeout=180,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"/interview/reply failed ({resp.status_code}): {resp.text}")
    return resp.json()


def _reply_stream(client: TestClient, session_id: str, message: str) -> dict[str, Any]:
    """
    Use streaming endpoint (/interview/reply-stream) and collect all events.
    Returns aggregated response with full agent message and extraction results.
    """
    resp = client.post(
        "/interview/reply-stream",
        json={"session_id": session_id, "user_message": message},
        timeout=180,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"/interview/reply-stream failed ({resp.status_code}): {resp.text}")
    
    # Parse Server-Sent Events
    agent_message = ""
    extraction_result = None
    error_msg = None
    
    for line in resp.text.split("\n"):
        if line.startswith("data: "):
            data_str = line[6:]
            if not data_str or data_str == "[DONE]":
                continue
            
            try:
                event = json.loads(data_str)
                event_type = event.get("type")
                
                if event_type == "chunk":
                    agent_message += event.get("data", "")
                    print(event.get("data", ""), end="", flush=True)
                
                elif event_type == "extraction":
                    extraction_result = event.get("data", {})
                
                elif event_type == "extraction_timeout":
                    print("\n[Note: Profile extraction taking longer than expected]", file=sys.stderr)
                
                elif event_type == "extraction_error":
                    error_msg = event.get("data", "Unknown extraction error")
                
                elif event_type == "error":
                    raise RuntimeError(f"Stream error: {event.get('data')}")
                
                elif event_type == "done":
                    pass
            
            except json.JSONDecodeError:
                pass
    
    # Return in same format as non-streaming endpoint
    return {
        "session_id": session_id,
        "agent_message": agent_message,
        "profile_completeness": extraction_result.get("profile_completeness", 0.0) if extraction_result else 0.0,
        "extracted_fields": extraction_result.get("extracted_fields", {}) if extraction_result else {},
    }


def _status(client: TestClient, session_id: str) -> dict[str, Any]:
    resp = client.get(
        "/interview/status",
        params={"session_id": session_id},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"/interview/status failed ({resp.status_code}): {resp.text}")
    return resp.json()


def _complete(client: TestClient, session_id: str, dilemma_override: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"session_id": session_id}
    if dilemma_override:
        payload["user_confirmed_dilemma"] = dilemma_override

    resp = client.post("/interview/complete", json=payload, timeout=180)
    if resp.status_code != 200:
        raise RuntimeError(f"/interview/complete failed ({resp.status_code}): {resp.text}")
    return resp.json()


def _start_exploration(client: TestClient, session_id: str, num_futures: int = 3) -> dict[str, Any]:
    resp = client.post(
        "/pipeline/start-exploration",
        json={"session_id": session_id, "num_futures": num_futures},
        timeout=300,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"/pipeline/start-exploration failed ({resp.status_code}): {resp.text}"
        )
    return resp.json()


def _pipeline_status(client: TestClient, session_id: str) -> dict[str, Any]:
    resp = client.get(f"/pipeline/status/{session_id}", timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"/pipeline/status failed ({resp.status_code}): {resp.text}")
    return resp.json()


def _conversation_reply(
    client: TestClient,
    session_id: str,
    self_id: str,
    message: str,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    resp = client.post(
        "/conversation/reply",
        json={
            "session_id": session_id,
            "self_id": self_id,
            "message": message,
            "history": history,
        },
        timeout=300,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"/conversation/reply failed ({resp.status_code}): {resp.text}")
    return resp.json()


def _branch_from_conversation(
    client: TestClient,
    session_id: str,
    parent_self_id: str,
    num_futures: int = 3,
) -> dict[str, Any]:
    resp = client.post(
        "/pipeline/branch-conversation",
        json={
            "session_id": session_id,
            "parent_self_id": parent_self_id,
            "num_futures": num_futures,
        },
        timeout=300,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"/pipeline/branch-conversation failed ({resp.status_code}): {resp.text}"
        )
    return resp.json()


def _get(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def _list_selves(selves: list[dict[str, Any]], current_self_id: str | None = None) -> None:
    if not selves:
        print("\nNo future selves available yet.")
        return

    print("\n=== Available Future Selves ===")
    for idx, self_card in enumerate(selves, start=1):
        self_id = str(self_card.get("id", ""))
        marker = " <- active" if current_self_id == self_id else ""
        name = str(self_card.get("name", "(unnamed)"))
        depth = self_card.get("depthLevel", self_card.get("depth_level", "?"))
        goal = str(
            self_card.get("optimizationGoal", self_card.get("optimization_goal", ""))
        )
        print(f"  [{idx}] {name} (id={self_id}, depth={depth}){marker}")
        if goal:
            print(f"      goal: {goal[:140]}")


def _print_commands() -> None:
    print("\nCommands:")
    print("  /help                      -> show all commands")
    print("  /status                    -> show status (onboarding or pipeline)")
    print("  /complete [dilemma text]   -> complete onboarding and auto-generate futures")
    print("  /selves                    -> list available future selves")
    print("  /use <index|self_id>       -> select active future self for conversation")
    print("  /branch [2-5]              -> branch from active self after conversation")
    print("  /quit                      -> exit")
    print("\nPlain text behavior:")
    print("  - During onboarding: sends message to interview agent")
    print("  - After /complete: sends message to selected future self")


def _default_messages() -> list[str]:
    return [
        "I’m 31, married, based in Amsterdam, and I work as a senior product manager in fintech.",
        "I was offered a role in Singapore with better pay and bigger scope, but my partner’s career is here.",
        "I value growth and financial security, but I’m afraid of damaging our relationship by forcing a move.",
        "Financially I’m around 140k total comp, and I’m pretty risk-tolerant in career but not in relationships.",
        "I’ve been stressed lately, sleep is inconsistent, and I feel pressure to not miss this opportunity.",
        "My core dilemma is: do I take the Singapore move to accelerate my career, or stay in Amsterdam to protect our life balance?",
    ]


def run_interactive(client: TestClient, session_id: str, user_name: str, use_streaming: bool = False) -> None:
    started = _start(client, session_id, user_name)
    print(f"\nSession: {session_id}")
    print(f"Mode: {'STREAMING' if use_streaming else 'Standard'}")
    print(f"Agent: {started.get('agent_message', '')}")

    phase = "onboarding"
    available_selves: list[dict[str, Any]] = []
    active_self_id: str | None = None
    histories_by_self: dict[str, list[dict[str, str]]] = {}

    _print_commands()

    while True:
        try:
            user_text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

        if not user_text:
            continue

        if user_text == "/quit":
            print("Exiting.")
            return

        if user_text == "/help":
            _print_commands()
            continue

        if user_text == "/status":
            if phase == "onboarding":
                s = _status(client, session_id)
                _print_json("Onboarding Status", s)
            else:
                s = _pipeline_status(client, session_id)
                _print_json("Pipeline Status", s)
            continue

        if user_text == "/selves":
            _list_selves(available_selves, current_self_id=active_self_id)
            continue

        if user_text.startswith("/use "):
            if not available_selves:
                print("No selves available yet. Run /complete first.")
                continue

            raw_target = user_text.split(" ", 1)[1].strip()
            chosen_id: str | None = None

            if raw_target.isdigit():
                idx = int(raw_target)
                if 1 <= idx <= len(available_selves):
                    chosen_id = str(available_selves[idx - 1].get("id", ""))
            else:
                candidate_ids = {str(s.get("id", "")) for s in available_selves}
                if raw_target in candidate_ids:
                    chosen_id = raw_target

            if not chosen_id:
                print("Invalid target. Use /selves and pick a valid index or self_id.")
                continue

            active_self_id = chosen_id
            if active_self_id not in histories_by_self:
                histories_by_self[active_self_id] = []
            _list_selves(available_selves, current_self_id=active_self_id)
            continue

        if user_text.startswith("/branch"):
            if phase == "onboarding":
                print("Complete onboarding first with /complete.")
                continue
            if not active_self_id:
                print("Pick an active self first with /use <index|self_id>.")
                continue

            parts = user_text.split()
            branch_count = 3
            if len(parts) > 1:
                try:
                    branch_count = int(parts[1])
                except ValueError:
                    print("Invalid branch count. Use /branch [2-5].")
                    continue
            if branch_count < 2 or branch_count > 5:
                print("Branch count must be between 2 and 5.")
                continue

            try:
                branch_data = _branch_from_conversation(
                    client,
                    session_id,
                    parent_self_id=active_self_id,
                    num_futures=branch_count,
                )
            except RuntimeError as exc:
                print(str(exc))
                continue

            parent_name = _get(branch_data, "parentSelfName", "parent_self_name", default="(unknown)")
            child_selves = _get(branch_data, "childSelves", "child_selves", default=[])
            print(f"\nBranched from: {parent_name}")
            print(f"Generated {len(child_selves)} child selves.")

            for child in child_selves:
                child_id = str(child.get("id", ""))
                if child_id not in {str(s.get('id', '')) for s in available_selves}:
                    available_selves.append(child)
                    histories_by_self[child_id] = []

            _list_selves(available_selves, current_self_id=active_self_id)
            continue

        if user_text.startswith("/complete"):
            if phase != "onboarding":
                print("Onboarding already completed. Use /selves, /use, and /branch.")
                continue

            dilemma_override = None
            parts = user_text.split(" ", 1)
            if len(parts) == 2 and parts[1].strip():
                dilemma_override = parts[1].strip()

            try:
                completed = _complete(client, session_id, dilemma_override)
            except RuntimeError as exc:
                print(str(exc))
                continue

            _print_json("Final User Profile", completed.get("userProfile", {}))
            _print_json("Generated Current Self", completed.get("currentSelf", {}))

            try:
                exploration = _start_exploration(client, session_id, num_futures=3)
            except RuntimeError as exc:
                print(str(exc))
                print("Onboarding is complete, but auto-start exploration failed.")
                continue

            future_selves = _get(exploration, "futureSelves", "future_selves", default=[])
            available_selves = list(future_selves)
            phase = "exploration"

            if available_selves:
                active_self_id = str(available_selves[0].get("id", ""))
                histories_by_self.setdefault(active_self_id, [])

            print("\nOnboarding complete. Exploration started automatically.")
            _list_selves(available_selves, current_self_id=active_self_id)
            print("Start chatting with plain text, switch with /use, and branch with /branch.")
            continue

        if user_text.startswith("/"):
            print("Unknown command. Type /help to see available commands.")
            continue

        if phase == "onboarding":
            print("Agent: ", end="", flush=True)
            reply_fn = _reply_stream if use_streaming else _reply
            r = reply_fn(client, session_id, user_text)
            if use_streaming:
                print()
            else:
                print(r.get("agentMessage", r.get("agent_message", "")))
            print(f"Completeness: {r.get('profileCompleteness', r.get('profile_completeness', 0.0)):.2f}")
            continue

        if not active_self_id:
            print("No active self selected. Use /selves and /use <index|self_id>.")
            continue

        history = histories_by_self.get(active_self_id, [])
        try:
            response = _conversation_reply(
                client,
                session_id=session_id,
                self_id=active_self_id,
                message=user_text,
                history=history,
            )
        except RuntimeError as exc:
            print(str(exc))
            continue

        reply_text = _get(response, "reply", default="")
        branch_name = _get(response, "branchName", "branch_name", default="")
        updated_history = _get(response, "history", default=[])
        histories_by_self[active_self_id] = updated_history

        if branch_name:
            print(f"[{branch_name}] {reply_text}")
        else:
            print(reply_text)


def run_scripted(client: TestClient, session_id: str, user_name: str, use_streaming: bool = False) -> None:
    started = _start(client, session_id, user_name)
    print(f"\nSession: {session_id}")
    print(f"Mode: {'STREAMING' if use_streaming else 'Standard'}")
    print(f"Agent: {started.get('agent_message', started.get('agentMessage', ''))}")

    for idx, msg in enumerate(_default_messages(), start=1):
        print(f"\nYou ({idx}): {msg}")
        print("Agent: ", end="", flush=True)
        reply_fn = _reply_stream if use_streaming else _reply
        r = reply_fn(client, session_id, msg)
        if use_streaming:
            print()  # Newline after streamed response
        else:
            print(r.get('agentMessage', r.get('agent_message', '')))
        print(f"Completeness: {r.get('profileCompleteness', r.get('profile_completeness', 0.0)):.2f}")
        time.sleep(0.15)

    s = _status(client, session_id)
    _print_json("Onboarding Status Before Complete", s)

    completed = _complete(client, session_id, dilemma_override=None)
    _print_json("Final User Profile", completed.get("userProfile", {}))
    _print_json("Generated Current Self", completed.get("currentSelf", {}))

    exploration = _start_exploration(client, session_id, num_futures=3)
    future_selves = _get(exploration, "futureSelves", "future_selves", default=[])
    print("\nOnboarding complete. Exploration started automatically.")
    _list_selves(future_selves)
    print("Use --mode interactive for live conversation and /branch commands.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Single CLI for live onboarding + auto exploration + conversation + branching."
        )
    )
    parser.add_argument(
        "--session-id",
        default=f"onboarding_live_{int(time.time())}",
        help="Session id written under storage.",
    )
    parser.add_argument("--user-name", "--username", dest="user_name", default="User")
    parser.add_argument(
        "--mode",
        choices=["interactive", "scripted"],
        default="interactive",
        help="Interactive chat or pre-filled scripted run.",
    )
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Use streaming endpoint (/interview/reply-stream) instead of standard endpoint.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    print("Running onboarding live test...")
    print("This uses real Mistral calls via your configured backend engines.")
    print("Single-file holistic flow: onboarding -> /complete -> auto exploration -> chat -> /branch")
    if args.streaming:
        print("Using STREAMING endpoint for real-time responses...")

    with TestClient(app) as client:
        if args.mode == "interactive":
            run_interactive(client, args.session_id, args.user_name, use_streaming=args.streaming)
        else:
            run_scripted(client, args.session_id, args.user_name, use_streaming=args.streaming)


if __name__ == "__main__":
    main()
