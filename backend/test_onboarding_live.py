from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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

    print("\nType your messages. Commands:")
    print("  /status   -> show extraction progress")
    print("  /complete -> finish onboarding and print userProfile + currentSelf")
    print("  /quit     -> exit without completing")

    while True:
        try:
            user_text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

        if not user_text:
            continue

        if user_text == "/quit":
            print("Exiting without completion.")
            return

        if user_text == "/status":
            s = _status(client, session_id)
            _print_json("Onboarding Status", s)
            continue

        if user_text.startswith("/complete"):
            dilemma_override = None
            parts = user_text.split(" ", 1)
            if len(parts) == 2 and parts[1].strip():
                dilemma_override = parts[1].strip()

            completed = _complete(client, session_id, dilemma_override)
            _print_json("Final User Profile", completed.get("userProfile", {}))
            _print_json("Generated Current Self", completed.get("currentSelf", {}))
            print("\nDone. Branching is intentionally not called in this script.")
            return

        print("Agent: ", end="", flush=True)
        reply_fn = _reply_stream if use_streaming else _reply
        r = reply_fn(client, session_id, user_text)
        if use_streaming:
            print()  # Newline after streamed response
        else:
            print(r.get('agentMessage', r.get('agent_message', '')))
        print(f"Completeness: {r.get('profileCompleteness', r.get('profile_completeness', 0.0)):.2f}")


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
    print("\nDone. Branching is intentionally not called in this script.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run full onboarding (live Mistral) and print userProfile + currentSelf without branching."
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
    if args.streaming:
        print("Using STREAMING endpoint for real-time responses...")

    with TestClient(app) as client:
        if args.mode == "interactive":
            run_interactive(client, args.session_id, args.user_name, use_streaming=args.streaming)
        else:
            run_scripted(client, args.session_id, args.user_name, use_streaming=args.streaming)


if __name__ == "__main__":
    main()
