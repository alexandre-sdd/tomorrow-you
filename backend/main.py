from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config.settings import get_settings
from backend.routers.conversation import router as conversation_router
from backend.routers.future_self import router as future_self_router
from backend.routers.onboarding import router as onboarding_router
from backend.routers.pipeline import router as pipeline_router

settings = get_settings()

app = FastAPI(
    title="Tomorrow You API",
    description="Future self persona generation and conversation backend.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboarding_router)
app.include_router(future_self_router)
app.include_router(conversation_router)
app.include_router(pipeline_router)

# Serve generated avatar images as static files.
# URL pattern: /avatars/{session_id}/avatars/{self_id}.png
avatar_storage_dir = Path(settings.storage_root)
avatar_storage_dir.mkdir(parents=True, exist_ok=True)
app.mount("/avatars", StaticFiles(directory=str(avatar_storage_dir)), name="avatars")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
