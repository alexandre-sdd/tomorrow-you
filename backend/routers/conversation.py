from __future__ import annotations

import asyncio
import base64
import binascii
import json
import re
from typing import Any, AsyncGenerator, Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from backend.config.runtime import get_runtime_config
from backend.config.settings import Settings, get_settings
from backend.engines import (
    BranchConversationSession,
    ContextResolver,
    ElevenLabsInterviewVoiceService,
    ElevenLabsVoiceError,
    MistralChatClient,
    MistralChatConfig,
    PromptComposer,
    PromptComposerConfig,
    append_conversation_turn,
    looks_like_placeholder_voice_id,
)
from backend.engines.context_resolver import ContextResolutionError
from backend.models.schemas import (
    ConversationTranscribeRequest,
    ConversationTranscribeResponse,
    ConversationTtsRequest,
    ConversationMessage,
    ConversationReplyRequest,
    ConversationReplyResponse,
)

router = APIRouter(prefix="/conversation", tags=["conversation"])


def _require_voice_enabled() -> None:
    if not get_runtime_config().interview_voice.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversation voice is disabled in runtime config.",
        )


def _validate_audio_mime(mime_type: str) -> str:
    normalized = (mime_type or "").strip().lower()
    if not normalized.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mimeType must be an audio/* content type.",
        )
    return normalized


def _decode_audio_base64(audio_base64: str) -> bytes:
    payload = (audio_base64 or "").strip()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="audioBase64 is required.",
        )

    if payload.startswith("data:"):
        try:
            payload = payload.split(",", 1)[1]
        except IndexError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed data URL for audioBase64.",
            ) from exc

    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 payload in audioBase64.",
        ) from exc


def _resolve_branch_context(
    resolver: ContextResolver,
    session_id: str,
    self_id: str,
) -> tuple[str, Any]:
    try:
        branch_name = resolver.find_branch_for_self(session_id, self_id)
    except ContextResolutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        context = resolver.resolve(session_id, branch_name)
    except ContextResolutionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return branch_name, context


def _normalized_text_for_gender(
    self_card: dict[str, Any],
    user_profile: dict[str, Any] | None = None,
) -> str:
    del self_card  # Gender inference should rely on user signals, not persona text.
    if not user_profile:
        return ""

    fields: tuple[Any, ...] = (
        user_profile.get("gender"),
        user_profile.get("sex"),
        user_profile.get("selfNarrative"),
        user_profile.get("self_narrative"),
        user_profile.get("currentDilemma"),
        user_profile.get("current_dilemma"),
        user_profile.get("relationships"),
        (user_profile.get("personal") or {}).get("relationships")
        if isinstance(user_profile.get("personal"), dict)
        else None,
    )

    parts = [value.strip().lower() for value in fields if isinstance(value, str) and value.strip()]
    return " ".join(parts)


def _normalize_gender_value(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip().lower()
    if not value:
        return None

    male_tokens = {"male", "man", "m", "cis male", "cis man"}
    female_tokens = {"female", "woman", "f", "cis female", "cis woman"}

    if value in male_tokens:
        return "male"
    if value in female_tokens:
        return "female"
    return None


def _infer_gender_from_self_identification(text: str) -> str | None:
    if not text:
        return None

    male_patterns = (
        r"\bi(?:\s+am|['’]m)\s+(?:a\s+)?man\b",
        r"\bi(?:\s+am|['’]m)\s+(?:a\s+)?male\b",
        r"\bi(?:\s+am|['’]m)\s+(?:a\s+)?guy\b",
        r"\bas\s+a\s+man\b",
        r"\bas\s+a\s+male\b",
    )
    female_patterns = (
        r"\bi(?:\s+am|['’]m)\s+(?:a\s+)?woman\b",
        r"\bi(?:\s+am|['’]m)\s+(?:a\s+)?female\b",
        r"\bi(?:\s+am|['’]m)\s+(?:a\s+)?girl\b",
        r"\bas\s+a\s+woman\b",
        r"\bas\s+a\s+female\b",
    )

    male_score = sum(1 for pattern in male_patterns if re.search(pattern, text))
    female_score = sum(1 for pattern in female_patterns if re.search(pattern, text))

    if male_score > female_score and male_score > 0:
        return "male"
    if female_score > male_score and female_score > 0:
        return "female"
    return None


def _infer_voice_gender(
    self_card: dict[str, Any],
    user_profile: dict[str, Any] | None = None,
) -> str | None:
    if user_profile:
        explicit_gender = _normalize_gender_value(user_profile.get("gender"))
        if explicit_gender:
            return explicit_gender

        explicit_sex = _normalize_gender_value(user_profile.get("sex"))
        if explicit_sex:
            return explicit_sex

        personal = user_profile.get("personal")
        if isinstance(personal, dict):
            personal_gender = _normalize_gender_value(personal.get("gender"))
            if personal_gender:
                return personal_gender

    text = _normalized_text_for_gender(self_card, user_profile)
    return _infer_gender_from_self_identification(text)


def _self_card_voice_id(self_card: dict[str, Any]) -> str:
    raw = self_card.get("voiceId")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    raw_snake = self_card.get("voice_id")
    if isinstance(raw_snake, str) and raw_snake.strip():
        return raw_snake.strip()
    return ""


def _conversation_voice_candidates(
    request: ConversationTtsRequest,
    self_card: dict[str, Any],
    user_profile: dict[str, Any] | None,
    settings: Settings,
) -> list[str]:
    candidate_ids: list[str] = []

    if request.voice_id:
        candidate_ids.append(request.voice_id.strip())

    gender = request.voice_gender or _infer_voice_gender(self_card, user_profile)
    if gender == "male" and settings.elevenlabs_chat_default_male_voice_id:
        candidate_ids.append(settings.elevenlabs_chat_default_male_voice_id.strip())
    if gender == "female" and settings.elevenlabs_chat_default_female_voice_id:
        candidate_ids.append(settings.elevenlabs_chat_default_female_voice_id.strip())

    card_voice_id = _self_card_voice_id(self_card)
    if card_voice_id and not looks_like_placeholder_voice_id(card_voice_id):
        candidate_ids.append(card_voice_id)

    candidate_ids.append(settings.elevenlabs_default_voice_id.strip())

    unique_valid: list[str] = []
    seen: set[str] = set()
    for candidate in candidate_ids:
        if not candidate:
            continue
        if looks_like_placeholder_voice_id(candidate):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        unique_valid.append(candidate)

    return unique_valid


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
    branch_name, context = _resolve_branch_context(
        resolver=resolver,
        session_id=request.session_id,
        self_id=request.self_id,
    )

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
    branch_name, context = _resolve_branch_context(
        resolver=resolver,
        session_id=request.session_id,
        self_id=request.self_id,
    )

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


@router.post("/transcribe", response_model=ConversationTranscribeResponse)
async def conversation_transcribe(
    request: ConversationTranscribeRequest,
    settings: Settings = Depends(get_settings),
) -> ConversationTranscribeResponse:
    """
    Transcribe one recorded conversation turn for a selected future self.
    """
    _require_voice_enabled()
    resolver = ContextResolver(storage_root=settings.storage_path)
    _resolve_branch_context(
        resolver=resolver,
        session_id=request.session_id,
        self_id=request.self_id,
    )

    runtime_voice = get_runtime_config().interview_voice
    mime_type = _validate_audio_mime(request.mime_type)
    audio_bytes = _decode_audio_base64(request.audio_base64)

    if len(audio_bytes) > runtime_voice.stt_max_audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Audio payload too large ({len(audio_bytes)} bytes). "
                f"Limit is {runtime_voice.stt_max_audio_bytes} bytes."
            ),
        )

    voice_service = ElevenLabsInterviewVoiceService()
    try:
        transcript = await asyncio.to_thread(
            voice_service.transcribe_bytes,
            audio_bytes,
            mime_type,
            request.language_code,
        )
    except ElevenLabsVoiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ConversationTranscribeResponse(
        session_id=request.session_id,
        self_id=request.self_id,
        transcript_text=transcript,
    )


@router.post("/tts")
async def conversation_tts(
    request: ConversationTtsRequest,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """
    Synthesize one future-self reply to speech with persona-aware voice selection.
    """
    _require_voice_enabled()
    text = request.text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="text must not be empty.",
        )

    resolver = ContextResolver(storage_root=settings.storage_path)
    _, context = _resolve_branch_context(
        resolver=resolver,
        session_id=request.session_id,
        self_id=request.self_id,
    )
    self_card = context.self_card if isinstance(context.self_card, dict) else {}
    candidate_voice_ids = _conversation_voice_candidates(
        request=request,
        self_card=self_card,
        user_profile=context.user_profile if isinstance(context.user_profile, dict) else None,
        settings=settings,
    )
    if not candidate_voice_ids:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "No valid conversation voice ID configured. "
                "Set ELEVENLABS_DEFAULT_VOICE_ID and optionally ELEVENLABS_CHAT_DEFAULT_MALE_VOICE_ID / "
                "ELEVENLABS_CHAT_DEFAULT_FEMALE_VOICE_ID in .env."
            ),
        )

    voice_service = ElevenLabsInterviewVoiceService()
    selected_voice_id = candidate_voice_ids[0]
    chunk_stream: Iterator[bytes] | None = None
    first_chunk = b""
    last_error: Exception | None = None

    for candidate_voice_id in candidate_voice_ids:
        try:
            attempted_stream = voice_service.synthesize_stream(
                text=text,
                voice_id=candidate_voice_id,
            )
            attempted_first_chunk = next(attempted_stream)
            selected_voice_id = candidate_voice_id
            chunk_stream = attempted_stream
            first_chunk = attempted_first_chunk
            last_error = None
            break
        except StopIteration:
            selected_voice_id = candidate_voice_id
            chunk_stream = iter(())
            first_chunk = b""
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            continue

    if chunk_stream is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(last_error) if last_error else "Text-to-speech failed.",
        )

    def _audio_stream() -> Iterator[bytes]:
        if first_chunk:
            yield first_chunk
        try:
            for chunk in chunk_stream:
                if chunk:
                    yield chunk
        except Exception:
            return

    return StreamingResponse(
        _audio_stream(),
        media_type=voice_service.tts_media_type(),
        headers={
            "Cache-Control": "no-store",
            "X-Conversation-Voice-Id": selected_voice_id,
        },
    )
