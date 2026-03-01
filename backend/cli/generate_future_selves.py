from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config.runtime import get_runtime_config
from backend.config.settings import get_settings
from backend.models.schemas import GenerateFutureSelvesRequest
from backend.routers.future_self import generate_future_selves

_runtime = get_runtime_config()
_future_runtime = _runtime.future_generation


def _load_dotenv_if_available() -> None:
    """Load .env from repo root for local CLI usage."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def build_parser() -> argparse.ArgumentParser:
    allowed_counts = sorted(_future_runtime.allowed_counts)
    parser = argparse.ArgumentParser(
        description=(
            "Generate future selves and persist them to session storage "
            "(same logic as POST /future-self/generate)."
        )
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help=f"Session ID under {_runtime.cli.storage_root}",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=_future_runtime.default_count,
        choices=allowed_counts,
        help="Number of futures to generate",
    )
    parser.add_argument(
        "--parent-self-id",
        default=None,
        help="Generate secondary futures from this parent self ID",
    )
    parser.add_argument(
        "--time-horizon",
        default=None,
        help="Optional horizon override (example: '2-3 years')",
    )
    return parser


async def run(args: argparse.Namespace) -> int:
    try:
        settings = get_settings()

        request = GenerateFutureSelvesRequest(
            session_id=args.session_id,
            count=args.count,
            parent_self_id=args.parent_self_id,
            time_horizon=args.time_horizon,
        )

        response = await generate_future_selves(request, settings)
    except Exception as exc:
        print(f"[generation error] {exc}")
        return 1

    print("Generation complete")
    print(f"  session_id: {response.session_id}")
    print(f"  generated_at: {response.generated_at}")
    print(f"  count: {len(response.future_self_options)}")
    print()
    print("Future selves:")

    for idx, card in enumerate(response.future_self_options, start=1):
        print(f"{idx}. {card.name}")
        print(f"   id: {card.id}")
        print(f"   depth: {card.depth_level}")
        print(f"   parent: {card.parent_self_id}")
        print(f"   mood: {card.visual_style.mood}")
        print(f"   goal: {card.optimization_goal}")
        print(f"   trade-off: {card.trade_off}")
        print()

    print("Next step (chat by self_id):")
    print(
        "  python3 -m backend.cli.chat_future_self "
        f"--session-id {response.session_id} "
        f"--self-id {response.future_self_options[0].id}"
    )

    return 0


def main() -> int:
    _load_dotenv_if_available()
    parser = build_parser()
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
