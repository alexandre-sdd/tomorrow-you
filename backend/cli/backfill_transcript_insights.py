from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config.runtime import get_runtime_config
from backend.config.settings import get_settings
from backend.engines.conversation_memory import analyze_and_persist_transcript_insights

_runtime = get_runtime_config()


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill transcript insights for one session by re-running "
            "conversation transcript analysis on branch nodes."
        )
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="Session ID under the storage root",
    )
    parser.add_argument(
        "--storage-root",
        default=_runtime.cli.storage_root,
        help="Session storage root",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Optional branch name to backfill (defaults to all non-root branches)",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not settings.mistral_api_key.strip():
        print("[setup error] MISTRAL_API_KEY is required")
        return 1

    session_dir = Path(args.storage_root) / args.session_id
    if not session_dir.exists():
        print(f"[error] session directory not found: {session_dir}")
        return 1

    branches_path = session_dir / "memory" / "branches.json"
    branches_raw = _read_json(branches_path)
    if not isinstance(branches_raw, list):
        print(f"[error] invalid branches file: {branches_path}")
        return 1

    target_branch_names: list[str] = []
    for raw in branches_raw:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if args.branch:
            if name == args.branch:
                target_branch_names.append(name)
        elif name != "root":
            target_branch_names.append(name)

    if args.branch and args.branch not in target_branch_names:
        print(f"[error] branch not found: {args.branch}")
        return 1
    if not target_branch_names:
        print("[info] no target branches to backfill")
        return 0

    branches_by_name = {
        raw.get("name"): raw
        for raw in branches_raw
        if isinstance(raw, dict) and isinstance(raw.get("name"), str)
    }

    processed = 0
    skipped = 0
    failed = 0
    total_added = 0
    print(
        f"Backfill transcript insights: session={args.session_id}, "
        f"branches={len(target_branch_names)}"
    )

    for branch_name in target_branch_names:
        branch = branches_by_name.get(branch_name) or {}
        head_node_id = branch.get("headNodeId")
        if not isinstance(head_node_id, str) or not head_node_id:
            print(f"- {branch_name}: skipped (missing headNodeId)")
            skipped += 1
            continue

        node_path = session_dir / "memory" / "nodes" / f"{head_node_id}.json"
        node = _read_json(node_path)
        if not isinstance(node, dict):
            print(f"- {branch_name}: skipped (missing node file {node_path.name})")
            skipped += 1
            continue

        self_card = node.get("selfCard")
        if not isinstance(self_card, dict):
            print(f"- {branch_name}: skipped (no selfCard on branch head)")
            skipped += 1
            continue
        self_id = self_card.get("id") if isinstance(self_card.get("id"), str) else None
        self_name = self_card.get("name") if isinstance(self_card.get("name"), str) else None
        if not self_id or not self_name:
            print(f"- {branch_name}: skipped (invalid selfCard id/name)")
            skipped += 1
            continue

        try:
            added = analyze_and_persist_transcript_insights(
                session_id=args.session_id,
                storage_root=args.storage_root,
                branch_name=branch_name,
                self_id=self_id,
                self_name=self_name,
                api_key=settings.mistral_api_key,
            )
        except Exception as exc:
            failed += 1
            print(
                f"- {branch_name}: self={self_name} ({self_id}), "
                f"error={exc}"
            )
            continue

        processed += 1
        total_added += len(added)
        print(
            f"- {branch_name}: self={self_name} ({self_id}), "
            f"insights_written={len(added)}"
        )

    print()
    print("Backfill summary")
    print(f"  processed: {processed}")
    print(f"  skipped: {skipped}")
    print(f"  failed: {failed}")
    print(f"  total insights written: {total_added}")
    return 1 if failed else 0


def main() -> int:
    _load_dotenv_if_available()
    parser = build_parser()
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
