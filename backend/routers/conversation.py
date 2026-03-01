from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

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


@router.post("/reply-stream")
async def conversation_reply_stream(
    request: ConversationReplyRequest,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """
    Send one message to a future self and receive a STREAMING reply.

    This endpoint provides real-time streaming of the conversation response:
    - Streams response token-by-token as they arrive from the LLM
    - Provides responsive, ChatGPT-like user experience
    - Maintains same conversation context as non-streaming endpoint
    
    Response format (Server-Sent Events):
        - {"type": "chunk", "data": "text chunk"} - Response text chunks
        - {"type": "done", "data": {"branch_name": "...", "full_reply": "..."}} - Complete
        - {"type": "error", "data": "error message"} - Error occurred
    
    Example client usage:
    ```javascript
    const response = await fetch('/conversation/reply-stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            session_id, self_id, message, history
        })
    });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        
        const text = decoder.decode(value);
        for (const line of text.split('\\n')) {
            if (line.startsWith('data: ')) {
                const event = JSON.parse(line.slice(6));
                if (event.type === 'chunk') {
                    displayMessage.append(event.data);
                } else if (event.type === 'done') {
                    // Streaming complete
                }
            }
        }
    }
    ```
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

    # Return streaming response
    return StreamingResponse(
        _stream_conversation_reply(
            session_id=request.session_id,
            self_id=request.self_id,
            branch_name=branch_name,
            context=context,
            message=request.message,
            history=request.history,
            settings=settings,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _stream_conversation_reply(
    session_id: str,
    self_id: str,
    branch_name: str,
    context: dict,
    message: str,
    history: list[ConversationMessage],
    settings: Settings,
) -> AsyncGenerator[str, None]:
    """
    Stream conversation reply chunks and persist transcript.
    
    Yields:
        - {"type": "chunk", "data": "text"} for each response chunk
        - {"type": "done", "data": {...}} when complete
        - {"type": "error", "data": "msg"} on error
    """
    # Build stateless engine objects
    composer = PromptComposer(PromptComposerConfig())
    client = MistralChatClient(
        api_key=settings.mistral_api_key,
        config=MistralChatConfig(model=settings.mistral_model),
    )

    # Pre-populate history from client, build session
    session = BranchConversationSession(
        context=context,
        composer=composer,
        client=client,
        history=[{"role": m.role, "content": m.content} for m in history],
    )

    # Stream response chunks
    try:
        full_reply_chunks: list[str] = []
        
        # Create an async generator from the blocking stream_reply
        # We need to yield chunks as they arrive, not collect them all first
        loop = asyncio.get_event_loop()
        
        # Use asyncio.to_thread to run blocking stream in thread pool
        # and yield chunks as they arrive
        def _sync_stream_generator():
            """Blocking generator that streams chunks from MistralClient"""
            for chunk in session.stream_reply(message):
                yield chunk
        
        # Convert blocking generator to async by running each iteration in thread
        gen = _sync_stream_generator()
        while True:
            try:
                # Get next chunk in a thread to avoid blocking event loop
                chunk = await loop.run_in_executor(None, lambda: next(gen, None))
                if chunk is None:
                    break
                
                full_reply_chunks.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"
            except StopIteration:
                break
        
        # Reconstruct full reply
        full_reply = "".join(full_reply_chunks).strip()
        
        # Persist to transcript (best-effort)
        self_name = context.self_card.get("name")
        try:
            append_conversation_turn(
                session_id=session_id,
                storage_root=settings.storage_path,
                branch_name=branch_name,
                self_id=self_id,
                self_name=self_name if isinstance(self_name, str) else None,
                user_text=message,
                assistant_text=full_reply,
            )
        except Exception:
            # Don't fail the stream if persistence fails
            pass
        
        # Send completion event
        yield f"data: {json.dumps({'type': 'done', 'data': {'branch_name': branch_name, 'full_reply': full_reply}})}\n\n"
        
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'data': str(exc)})}\n\n"
