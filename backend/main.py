from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
