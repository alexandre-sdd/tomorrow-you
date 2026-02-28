from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.engines import (
    BranchConversationSession,
    ContextResolver,
    MistralChatClient,
    MistralChatConfig,
    PromptComposer,
    PromptComposerConfig,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chat with a selected future-self branch using Mistral (CLI MVP)."
    )
    parser.add_argument("--session-id", required=True, help="Session ID under storage/sessions")
    parser.add_argument("--branch", required=True, help="Branch name in memory/branches.json")
    parser.add_argument(
        "--storage-root",
        default="storage/sessions",
        help="Session storage root directory",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MISTRAL_API_KEY", ""),
        help="Mistral API key (defaults to MISTRAL_API_KEY)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
        help="Mistral model name",
    )
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--max-tokens", type=int, default=220)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-memory-facts", type=int, default=10)
    parser.add_argument("--max-memory-notes", type=int, default=6)
    parser.add_argument("--max-history-turns", type=int, default=8)
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming output")
    return parser


def run(args: argparse.Namespace) -> int:
    try:
        resolver = ContextResolver(storage_root=args.storage_root)
        context = resolver.resolve(session_id=args.session_id, branch_name=args.branch)

        composer = PromptComposer(
            PromptComposerConfig(
                max_memory_facts=args.max_memory_facts,
                max_memory_notes=args.max_memory_notes,
                max_history_turns=args.max_history_turns,
            )
        )

        client = MistralChatClient(
            api_key=args.api_key,
            config=MistralChatConfig(
                model=args.model,
                temperature=args.temperature,
                top_p=args.top_p,
                max_tokens=args.max_tokens,
                timeout_seconds=args.timeout,
            ),
        )
    except Exception as exc:
        print(f"[setup error] {exc}")
        return 1

    session = BranchConversationSession(context=context, composer=composer, client=client)
    _print_banner(session)

    while True:
        try:
            user_text = input("You > ").strip()
        except EOFError:
            print("\nExiting.")
            return 0
        except KeyboardInterrupt:
            print("\nExiting.")
            return 0

        if not user_text:
            continue

        if user_text in {"/exit", "/quit"}:
            print("Exiting.")
            return 0

        if user_text == "/reset":
            session.reset()
            print("History reset.")
            continue

        if user_text == "/context":
            _print_context(session)
            continue

        try:
            if args.no_stream:
                reply = session.reply(user_text)
                print(f"Future Self > {reply}\n")
            else:
                print("Future Self > ", end="", flush=True)
                had_output = False
                for chunk in session.stream_reply(user_text):
                    had_output = True
                    print(chunk, end="", flush=True)
                if not had_output:
                    print("[no output]", end="", flush=True)
                print("\n")
        except KeyboardInterrupt:
            print("\nInterrupted current turn.\n")
        except Exception as exc:
            print(f"\n[turn error] {exc}\n")


def _print_banner(session: BranchConversationSession) -> None:
    info = session.describe_context()
    print("Future Selves CLI MVP")
    print(f"Session: {info['session_id']}")
    print(f"Branch: {info['branch_name']}")
    print(f"Persona: {info['self_name']}")
    print("Commands: /context, /reset, /exit")
    print()


def _print_context(session: BranchConversationSession) -> None:
    info = session.describe_context()
    print("Context")
    print(f"  session: {info['session_id']}")
    print(f"  branch: {info['branch_name']}")
    print(f"  self: {info['self_name']}")
    print(f"  goal: {info['optimization_goal']}")
    print(f"  worldview: {info['worldview']}")
    print(f"  trade-off: {info['trade_off']}")
    print(f"  memory facts: {info['memory_facts']}")
    print(f"  memory notes: {info['memory_notes']}")
    print(f"  history messages: {info['history_messages']}")
    print()


def main() -> int:
    parser = build_parser()
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
