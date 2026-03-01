"""
Tomorrow You Backend API

FastAPI application server with all routers integrated.
Handles interview onboarding, profile extraction, future self generation, and conversation.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import get_settings
from backend.routers import conversation, future_self, onboarding, pipeline

# ---------------------------------------------------------------------------
# App initialization
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="Tomorrow You API",
        description="Explore your future selves through deliberate life dilemmas",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(onboarding.router)  # /interview/* endpoints
    app.include_router(future_self.router)  # /future-self/* endpoints
    app.include_router(conversation.router)  # /conversation/* endpoints
    app.include_router(pipeline.router)  # /pipeline/* endpoints
    
    # Health check
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy"}
    
    return app


# Singleton app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
