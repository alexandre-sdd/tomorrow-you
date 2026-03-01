from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config.runtime import get_runtime_config
from backend.config.settings import get_settings
from backend.engines import (
    BranchConversationSession,
    ContextResolver,
    MistralChatClient,
    MistralChatConfig,
    PromptComposer,
    PromptComposerConfig,
)
from backend.models.schemas import GenerateFutureSelvesRequest, SelfCard
from backend.routers.future_self import generate_future_selves

_runtime = get_runtime_config()
_chat_runtime = _runtime.mistral_chat
_prompt_runtime = _runtime.prompt_composer
_cli_runtime = _runtime.cli
_future_runtime = _runtime.future_generation


def _load_dotenv_if_available() -> None:
    """
    Load .env from repo root for local CLI usage.

    This keeps CLI ergonomics simple (no manual `export ...` needed).
    """
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chat with a selected future-self branch using Mistral (CLI MVP)."
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help=f"Session ID under {_cli_runtime.storage_root}",
    )
    target_group = parser.add_mutually_exclusive_group(required=False)
    target_group.add_argument(
        "--branch",
        help="Branch name in memory/branches.json",
    )
    target_group.add_argument(
        "--self-id",
        help="Future self ID (auto-resolves branch name from memory tree)",
    )
    parser.add_argument(
        "--storage-root",
        default=_cli_runtime.storage_root,
        help="Session storage root directory",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MISTRAL_API_KEY", ""),
        help="Mistral API key (defaults to MISTRAL_API_KEY)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("MISTRAL_MODEL", _chat_runtime.model),
        help="Mistral model name",
    )
    parser.add_argument("--temperature", type=float, default=_chat_runtime.temperature)
    parser.add_argument("--top-p", type=float, default=_chat_runtime.top_p)
    parser.add_argument("--max-tokens", type=int, default=_chat_runtime.max_tokens)
    parser.add_argument("--timeout", type=float, default=_chat_runtime.timeout_seconds)
    parser.add_argument("--max-memory-facts", type=int, default=_prompt_runtime.max_memory_facts)
    parser.add_argument("--max-memory-notes", type=int, default=_prompt_runtime.max_memory_notes)
    parser.add_argument("--max-history-turns", type=int, default=_prompt_runtime.max_history_turns)
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming output")
    return parser


def run(args: argparse.Namespace) -> int:
    try:
        resolver = ContextResolver(storage_root=args.storage_root)
        if args.self_id:
            branch_name = resolver.find_branch_for_self(args.session_id, args.self_id)
        elif args.branch:
            branch_name = args.branch
        else:
            chosen = _choose_starting_persona(
                session_id=args.session_id,
                storage_root=args.storage_root,
                resolver=resolver,
            )
            if chosen is None:
                return 1
            branch_name = resolver.find_branch_for_self(args.session_id, chosen.id)
            print(f"Selected starting persona: {chosen.name} ({chosen.id})")
        context = resolver.resolve(session_id=args.session_id, branch_name=branch_name)

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
    last_user_message: str | None = None

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

        if user_text == "/help":
            _print_help()
            continue

        if user_text == "/reset":
            session.reset()
            print("History reset for current branch.")
            continue

        if user_text == "/context":
            _print_context(session)
            continue

        if user_text == "/reprompt":
            if not last_user_message:
                print("No previous user prompt available to reprompt.\n")
                continue
            print(f"Reprompting same message: {last_user_message}")
            if not _execute_turn(session, last_user_message, no_stream=args.no_stream):
                continue
            print()
            continue

        if user_text.startswith("/branch-reprompt"):
            session = _branch_and_choose(
                command=user_text,
                session=session,
                resolver=resolver,
                composer=composer,
                client=client,
                session_id=args.session_id,
                auto_reprompt=True,
                reprompt_text=last_user_message,
                no_stream=args.no_stream,
            )
            print()
            continue

        if user_text.startswith("/branch"):
            session = _branch_and_choose(
                command=user_text,
                session=session,
                resolver=resolver,
                composer=composer,
                client=client,
                session_id=args.session_id,
                auto_reprompt=False,
                reprompt_text=None,
                no_stream=args.no_stream,
            )
            print()
            continue

        last_user_message = user_text
        if not _execute_turn(session, user_text, no_stream=args.no_stream):
            continue
        print()


def _execute_turn(session: BranchConversationSession, user_text: str, no_stream: bool) -> bool:
    try:
        if no_stream:
            reply = session.reply(user_text)
            print(f"Future Self > {reply}")
            return True

        print("Future Self > ", end="", flush=True)
        had_output = False
        for chunk in session.stream_reply(user_text):
            had_output = True
            print(chunk, end="", flush=True)
        if not had_output:
            print("[no output]", end="", flush=True)
        print()
        return True
    except KeyboardInterrupt:
        print("\nInterrupted current turn.")
        return False
    except Exception as exc:
        print(f"\n[turn error] {exc}")
        return False


def _branch_and_choose(
    *,
    command: str,
    session: BranchConversationSession,
    resolver: ContextResolver,
    composer: PromptComposer,
    client: MistralChatClient,
    session_id: str,
    auto_reprompt: bool,
    reprompt_text: str | None,
    no_stream: bool,
) -> BranchConversationSession:
    parent_self_id = session.context.self_card.get("id")
    if not isinstance(parent_self_id, str) or not parent_self_id:
        print("Cannot branch: current context has no valid self ID.")
        return session

    count, time_horizon = _parse_branch_command(command)
    if count is None:
        return session

    try:
        settings = get_settings()
        request = GenerateFutureSelvesRequest(
            session_id=session_id,
            count=count,
            parent_self_id=parent_self_id,
            time_horizon=time_horizon,
        )
        response = asyncio.run(generate_future_selves(request, settings))
    except Exception as exc:
        print(f"[branch error] {exc}")
        return session

    options = list(response.future_self_options)
    if not options:
        print("No futures were generated.")
        return session

    print("Generated futures:")
    for idx, card in enumerate(options, start=1):
        print(f"{idx}. {card.name}")
        print(f"   id: {card.id}")
        print(f"   depth: {card.depth_level}")
        print(f"   goal: {card.optimization_goal}")
        print(f"   trade-off: {card.trade_off}")

    selected = _prompt_select_option(options)
    if selected is None:
        print("No path selected. Staying on current branch.")
        return session

    try:
        new_branch_name = resolver.find_branch_for_self(session_id, selected.id)
        new_context = resolver.resolve(session_id=session_id, branch_name=new_branch_name)
        new_session = BranchConversationSession(context=new_context, composer=composer, client=client)
    except Exception as exc:
        print(f"[branch switch error] {exc}")
        return session

    print(f"Switched to: {selected.name} (branch: {new_branch_name})")
    print("History reset for new branch.")

    if auto_reprompt:
        if not reprompt_text:
            print("No previous prompt available to reprompt on new branch.")
        else:
            print(f"Reprompting on new branch: {reprompt_text}")
            _execute_turn(new_session, reprompt_text, no_stream=no_stream)

    return new_session


def _parse_branch_command(command: str) -> tuple[int | None, str | None]:
    """
    Parse `/branch [count] [time horizon...]` style commands.

    Examples:
    - /branch
    - /branch 3
    - /branch 2 2-3 years
    """
    parts = command.split(maxsplit=2)
    count = _cli_runtime.branch_default_count
    time_horizon: str | None = None
    allowed = set(_future_runtime.allowed_counts)

    if len(parts) >= 2:
        raw_count = parts[1].strip()
        try:
            count = int(raw_count)
        except ValueError:
            choices = "|".join(str(v) for v in sorted(allowed))
            print(f"Invalid branch count. Use /branch [{choices}] [optional time horizon]")
            return None, None
        if count not in allowed:
            choices = ", ".join(str(v) for v in sorted(allowed))
            print(f"Branch count must be one of: {choices}.")
            return None, None

    if len(parts) == 3:
        tail = parts[2].strip()
        time_horizon = tail or None

    return count, time_horizon


def _prompt_select_option(options: Iterable[SelfCard]) -> SelfCard | None:
    items = list(options)
    index_map = {str(i): card for i, card in enumerate(items, start=1)}
    id_map = {card.id: card for card in items}

    while True:
        raw = input("Choose option (index or self_id, Enter to cancel): ").strip()
        if not raw:
            return None
        if raw in index_map:
            return index_map[raw]
        if raw in id_map:
            return id_map[raw]
        print("Invalid selection. Enter a valid index or self_id.")


def _choose_starting_persona(
    *,
    session_id: str,
    storage_root: str,
    resolver: ContextResolver,
) -> SelfCard | None:
    """
    Prompt the user to pick an existing future-self persona when no --self-id/--branch is supplied.
    """
    session_file = Path(storage_root) / session_id / "session.json"
    if not session_file.exists():
        print(f"[setup error] Session not found: {session_file}")
        return None

    try:
        session_data = json.loads(session_file.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[setup error] Failed to read session data: {exc}")
        return None

    candidates: list[SelfCard] = []
    seen_ids: set[str] = set()

    def _try_add(raw_card: object) -> None:
        if not isinstance(raw_card, dict):
            return
        try:
            card = SelfCard.model_validate(raw_card)
        except Exception:
            return
        if card.type != "future":
            return
        if card.id in seen_ids:
            return
        try:
            resolver.find_branch_for_self(session_id, card.id)
        except Exception:
            return
        seen_ids.add(card.id)
        candidates.append(card)

    for raw in session_data.get("futureSelfOptions", []):
        _try_add(raw)

    full = session_data.get("futureSelvesFull", {})
    if isinstance(full, dict):
        for raw in full.values():
            _try_add(raw)

    if not candidates:
        print("No selectable future-self personas found in session.")
        print("Generate futures first, then start chat with --self-id or rerun this command.")
        return None

    print("Available personas:")
    for idx, card in enumerate(candidates, start=1):
        print(f"{idx}. {card.name}")
        print(f"   id: {card.id}")
        print(f"   depth: {card.depth_level}")
        print(f"   goal: {card.optimization_goal}")

    selected = _prompt_select_option(candidates)
    if selected is None:
        print("No persona selected.")
    return selected


def _print_banner(session: BranchConversationSession) -> None:
    info = session.describe_context()
    print("Future Selves CLI MVP")
    print(f"Session: {info['session_id']}")
    print(f"Branch: {info['branch_name']}")
    print(f"Persona: {info['self_name']}")
    print("Commands: /context, /reset, /branch, /branch-reprompt, /reprompt, /help, /exit")
    print()


def _print_help() -> None:
    choices = "|".join(str(v) for v in sorted(_future_runtime.allowed_counts))
    print("Commands")
    print("  /context")
    print("    Show current branch and persona context")
    print("  /reset")
    print("    Clear in-memory history for current branch")
    print(f"  /branch [{choices}] [optional time horizon]")
    print("    Generate child futures from current self and choose one path")
    print(f"  /branch-reprompt [{choices}] [optional time horizon]")
    print("    Same as /branch, then re-ask your last user message on chosen path")
    print("  /reprompt")
    print("    Re-ask your last user message on current branch")
    print("  /help")
    print("    Show this help")
    print("  /exit")
    print("    Exit chat")
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
    _load_dotenv_if_available()
    parser = build_parser()
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
