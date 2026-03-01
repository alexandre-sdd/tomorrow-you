"""
Legacy Interview Router

Placeholder for future interview-related endpoints.
Onboarding logic is now in routers/onboarding.py.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/interview-legacy", tags=["interview-legacy"])


@router.get("/")
async def list_interview_endpoints() -> dict[str, str]:
    """List available interview endpoints."""
    return {
        "message": "Interview endpoints moved to /interview/*",
        "note": "See onboarding.py for current implementation",
    }
