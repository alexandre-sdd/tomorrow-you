#!/usr/bin/env python3
"""
One-command launcher for the full interactive CLI pipeline.

Flow:
1) Runs interactive onboarding for a generated session ID.
2) If onboarding is completed (/complete), automatically launches full pipeline demo.

Usage:
  python run_full_cli_pipeline.py
  python run_full_cli_pipeline.py --user-name Matt
  python run_full_cli_pipeline.py --session-id my_session_001
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_STORAGE = REPO_ROOT / "storage" / "sessions"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run onboarding, then auto-open full interactive pipeline CLI."
    )
    parser.add_argument(
        "--session-id",
        default=f"full_cli_{int(time.time())}",
        help="Session ID to use for both onboarding and full pipeline demo.",
    )
    parser.add_argument(
        "--user-name",
        "--username",
        dest="user_name",
        default="User",
        help="Name used during onboarding.",
    )
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Use streaming onboarding endpoint.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use (default: current interpreter).",
    )
    return parser


def _session_file(session_id: str) -> Path:
    return DEFAULT_STORAGE / session_id / "session.json"


def _has_current_self(session_id: str) -> bool:
    session_path = _session_file(session_id)
    if not session_path.exists():
        return False
    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(data.get("currentSelf"))


def run_onboarding(python_bin: str, session_id: str, user_name: str, streaming: bool) -> int:
    cmd = [
        python_bin,
        str(REPO_ROOT / "backend" / "test_onboarding_live.py"),
        "--mode",
        "interactive",
        "--session-id",
        session_id,
        "--user-name",
        user_name,
    ]
    if streaming:
        cmd.append("--streaming")

    print("\n" + "=" * 70)
    print("STEP 1: INTERACTIVE ONBOARDING")
    print("=" * 70)
    print(f"Session ID: {session_id}")
    print("When ready, type /complete in onboarding to continue automatically.\n")

    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


def run_full_demo(python_bin: str, session_id: str) -> int:
    cmd = [
        python_bin,
        str(REPO_ROOT / "backend" / "cli" / "full_pipeline_demo.py"),
        "--session-id",
        session_id,
    ]

    print("\n" + "=" * 70)
    print("STEP 2: FULL INTERACTIVE PIPELINE")
    print("=" * 70)
    print("Launching full CLI demo...\n")

    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


def main() -> int:
    args = build_parser().parse_args()

    python_bin = args.python
    if not shutil_which_or_exists(python_bin):
        print(f"ERROR: Python executable not found: {python_bin}")
        return 1

    print("\nOne-command full CLI pipeline launcher")
    print(f"Repo: {REPO_ROOT}")
    print(f"Python: {python_bin}")

    onboarding_exit = run_onboarding(
        python_bin=python_bin,
        session_id=args.session_id,
        user_name=args.user_name,
        streaming=args.streaming,
    )

    if onboarding_exit != 0:
        print(f"\nOnboarding exited with code {onboarding_exit}.")
        print("Fix onboarding errors and re-run this launcher.")
        return onboarding_exit

    if not _has_current_self(args.session_id):
        print("\nOnboarding ended before completion (no currentSelf found in session).")
        print("Re-run and finish onboarding with /complete.")
        return 1

    return run_full_demo(python_bin=python_bin, session_id=args.session_id)


def shutil_which_or_exists(python_bin: str) -> bool:
    if os.path.sep in python_bin:
        return Path(python_bin).exists()
    from shutil import which

    return which(python_bin) is not None


if __name__ == "__main__":
    raise SystemExit(main())
