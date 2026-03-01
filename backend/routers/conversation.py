from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from backend.config.settings import Settings, get_settings
from backend.engines import (
    BranchConversationSession,
    ContextResolver,
    MistralChatClient,
    MistralChatConfig,
    PromptComposer,
    PromptComposerConfig,
    append_conversation_turn,
)
from backend.engines.context_resolver import ContextResolutionError
from backend.models.schemas import (
    ConversationMessage,
    ConversationReplyRequest,
    ConversationReplyResponse,
)

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.post("/reply", response_model=ConversationReplyResponse)
async def conversation_reply(
    request: ConversationReplyRequest,
    settings: Settings = Depends(get_settings),
) -> ConversationReplyResponse:
    """
    Send one message to a future self and receive a reply.

    Client owns conversation history — send the full history on every call.
    Returns the updated history (original + new user + new assistant turns).
    Request handling stays stateless for turn assembly, while transcript
    persistence is written as a best-effort side effect.
    """
    # 1. Resolve branch_name from self_id
    resolver = ContextResolver(storage_root=settings.storage_path)
    try:
        branch_name = resolver.find_branch_for_self(request.session_id, request.self_id)
    except ContextResolutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # 2. Resolve conversation context from the memory tree
    try:
        context = resolver.resolve(request.session_id, branch_name)
    except ContextResolutionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 3. Build stateless engine objects (constructed per-request — no shared mutable state)
    composer = PromptComposer(PromptComposerConfig())
    client = MistralChatClient(
        api_key=settings.mistral_api_key,
        config=MistralChatConfig(model=settings.mistral_model),
    )

    # 4. Pre-populate history from client, build session
    session = BranchConversationSession(
        context=context,
        composer=composer,
        client=client,
        history=[{"role": m.role, "content": m.content} for m in request.history],
    )

    # 5. MistralChatClient uses blocking urllib — run off the async event loop
    try:
        reply_text = await asyncio.to_thread(session.reply, request.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    # 6. Return updated history — client replaces its stored copy with this
    self_name = context.self_card.get("name")
    try:
        append_conversation_turn(
            session_id=request.session_id,
            storage_root=settings.storage_path,
            branch_name=branch_name,
            self_id=request.self_id,
            self_name=self_name if isinstance(self_name, str) else None,
            user_text=request.message,
            assistant_text=reply_text,
        )
    except Exception:
        # Best-effort persistence; do not fail the request if storage write fails.
        pass

    updated_history = [
        *request.history,
        ConversationMessage(role="user", content=request.message),
        ConversationMessage(role="assistant", content=reply_text),
    ]

    return ConversationReplyResponse(
        session_id=request.session_id,
        self_id=request.self_id,
        branch_name=branch_name,
        reply=reply_text,
        history=updated_history,
    )
