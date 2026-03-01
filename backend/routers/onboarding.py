"""
Onboarding Router

Endpoints for interview-driven onboarding with incremental profile extraction
and auto-generation of CurrentSelf when ready.

Flow:
1. POST /interview/start -> Initialize interview session
2. POST /interview/reply -> User message -> Interview agent response + Extract profile
3. POST /interview/reply-stream -> User message -> Stream agent response + Extract in parallel
4. GET /interview/status -> Check profile completeness
5. POST /interview/complete -> Generate CurrentSelf + return ready for future-self gen
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from mistralai import Mistral

from backend.config.settings import get_settings
from backend.engines.current_self_auto_generator import (
    CurrentSelfAutoGeneratorEngine,
    CurrentSelfGenerationContext,
)
from backend.engines.profile_extractor import (
    ExtractionContext,
    ProfileExtractorEngine,
)
from backend.models.schemas import (
    InterviewCompleteRequest,
    InterviewCompleteResponse,
    InterviewReplyRequest,
    InterviewReplyResponse,
    InterviewStartRequest,
    InterviewStatusResponse,
    SelfCard,
    UserProfile,
)


# ---------------------------------------------------------------------------
# Session storage helpers
# ---------------------------------------------------------------------------

def _get_session_path(session_id: str) -> Path:
    """Get path to session.json file."""
    return Path(get_settings().storage_root) / session_id / "session.json"


def _load_session(session_id: str) -> dict[str, Any]:
    """Load session from disk."""
    path = _get_session_path(session_id)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    with open(path) as f:
        return json.load(f)


def _save_session(session_id: str, session_data: dict[str, Any]) -> None:
    """Save session to disk, updating timestamp."""
    session_data["updatedAt"] = time.time()
    path = _get_session_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(session_data, f, indent=2)


def _initialize_memory_tree(session_id: str, current_self: SelfCard) -> None:
    """
    Initialize memory tree structure with root node.
    
    Creates memory/nodes/ directory and root node with currentSelf.
    This is called when onboarding completes.
    """
    settings = get_settings()
    session_dir = Path(settings.storage_root) / session_id
    nodes_dir = session_dir / "memory" / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    
    # Create root node with currentSelf
    now = time.time()
    root_node_id = "root_node"
    
    root_node = {
        "id": root_node_id,
        "parentId": None,  # Root has no parent
        "branchLabel": "root",
        "facts": [
            {
                "id": f"fact_{root_node_id}_0",
                "fact": f"Current self: {current_self.name}",
                "source": "onboarding",
                "extractedAt": now,
            },
            {
                "id": f"fact_{root_node_id}_1",
                "fact": f"Optimization goal: {current_self.optimization_goal}",
                "source": "onboarding",
                "extractedAt": now,
            }
        ],
        "notes": ["Root node created during onboarding"],
        "selfCard": current_self.model_dump(by_alias=True),
        "createdAt": now,
    }
    
    # Write root node
    root_node_file = nodes_dir / f"{root_node_id}.json"
    root_node_file.write_text(json.dumps(root_node, indent=2), encoding="utf-8")
    
    # Initialize branches.json with root branch
    branches_file = session_dir / "memory" / "branches.json"
    branches = [
        {
            "name": "root",
            "headNodeId": root_node_id,
            "parentBranchName": None,
        }
    ]
    branches_file.write_text(json.dumps(branches, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Interview session cache (in-memory)
# ---------------------------------------------------------------------------

_INTERVIEW_HISTORIES: dict[str, list[dict[str, str]]] = {}


def _load_interview_system_prompt() -> str:
    """Load interview agent system prompt from prompts/interview_agent.md."""
    prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "interview_agent.md"
    return prompt_path.read_text() if prompt_path.exists() else ""


def _initialize_interview_session(
    session_id: str,
    user_name: str,
    existing_profile: UserProfile | None = None,
) -> list[dict[str, str]]:
    """Create interview conversation session in memory."""
    history: list[dict[str, str]] = []

    # Seed with opening if first time
    if not existing_profile:
        greeting = f"Hello {user_name}! I'm here to get to know you and understand what brought you here today. Tell me—what's going on in your life right now that made you come to Tomorrow You?"
        history.append({"role": "assistant", "content": greeting})

    _INTERVIEW_HISTORIES[session_id] = history
    return history


def _build_interview_messages(
    history: list[dict[str, str]],
    user_message: str,
    system_prompt: str = "",
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    clipped_history = history[-16:]
    for msg in clipped_history:
        role = msg.get("role", "")
        content = msg.get("content", "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message.strip()})
    return messages


def _normalize_agent_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()
    return ""


def _is_handoff_style_message(message: str) -> bool:
    """Detect interview-closing language that should be blocked when profile is sparse."""
    text = message.lower().strip()
    markers = (
        "i'm handing this off",
        "im handing this off",
        "i'll pass this along",
        "ill pass this along",
        "i've got a solid picture",
        "ive got a solid picture",
        "build out your future scenarios",
    )
    return any(marker in text for marker in markers)


def _build_deepening_followup(profile: UserProfile | None) -> str:
    """Build one focused follow-up question to gather missing high-value signal."""
    if not profile:
        return (
            "Before I hand this off, I need one more detail to personalize your scenarios. "
            "When you're making high-stakes decisions, what value matters most to you?"
        )

    if not profile.core_values and not profile.personal.personal_values:
        return (
            "Before I hand this off, one key piece is still missing. "
            "What matters most to you in this decision right now—security, growth, stability, impact, or something else?"
        )

    if not profile.decision_style and not profile.self_narrative:
        return (
            "I want one more signal before we hand this off. "
            "When you face a big decision like this, do you usually move fast and trust your gut, or slow down and analyze every trade-off?"
        )

    if not profile.financial.money_mindset:
        return (
            "Before we hand off, I need your money lens on this. "
            "In this choice, are you more focused on immediate stability or on taking financial risk for long-term upside?"
        )

    if not profile.personal.relationships:
        return (
            "Before we hand this off, one more context piece helps a lot. "
            "Who else is most affected by this decision, and how much weight does their situation carry for you?"
        )

    return (
        "I can hand this off in a second, but one last detail will make the scenarios sharper. "
        "What's the biggest constraint that makes this decision hard right now?"
    )


def _apply_handoff_blocker(
    agent_message: str,
    profile_completeness: float,
    profile: UserProfile | None,
) -> str:
    """Prevent handoff-style closing when profile completeness is below 50%."""
    if profile_completeness < 0.5 and _is_handoff_style_message(agent_message):
        return _build_deepening_followup(profile)
    return agent_message


async def _generate_interview_reply(
    history: list[dict[str, str]],
    user_message: str,
) -> str:
    settings = get_settings()
    client = Mistral(api_key=settings.mistral_api_key)

    system_prompt = _load_interview_system_prompt()
    messages = _build_interview_messages(history, user_message, system_prompt)
    response = await client.chat.complete_async(
        model="mistral-small-latest",
        messages=messages,  # pyright: ignore
        temperature=0.7,
        max_tokens=500,
    )
    assistant_text = _normalize_agent_content(response.choices[0].message.content)
    if not assistant_text:
        raise RuntimeError("Received empty interview response")

    history.append({"role": "user", "content": user_message.strip()})
    history.append({"role": "assistant", "content": assistant_text})
    return assistant_text


async def _stream_interview_reply_with_chat_api(
    history: list[dict[str, str]],
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Stream interview agent response using Mistral chat API for true token streaming.
    Falls back to chunked response if needed.
    
    Yields text chunks as they arrive from the API.
    """
    from backend.engines.mistral_client import MistralChatClient, MistralChatConfig
    
    settings = get_settings()

    system_prompt = _load_interview_system_prompt()
    # Build messages for chat API
    messages = _build_interview_messages(history, user_message, system_prompt)

    # Add user to history first
    history.append({"role": "user", "content": user_message.strip()})
    
    # Create chat client - use chat API instead of agent API for streaming
    try:
        chat_client = MistralChatClient(
            api_key=settings.mistral_api_key,
            config=MistralChatConfig(
                model="mistral-small-latest",
                temperature=0.7,
                top_p=0.95,
                max_tokens=500,
            )
        )
        
        # Stream response from chat API
        full_response = ""
        for chunk in chat_client.stream_chat(messages):  # pyright: ignore
            if chunk:
                full_response += chunk
                yield chunk
        
        # Add complete response to history
        if full_response:
            history.append({"role": "assistant", "content": full_response})
    except Exception as exc:
        # Fallback: use agent API with chunking
        print(f"Streaming fallback: {exc}")
        if not settings.mistral_agent_id_interview.strip():
            raise RuntimeError(
                "MISTRAL_AGENT_ID_INTERVIEW is not configured. "
                "Set it in .env to use the preconfigured interview agent prompt."
            )
        
        client = Mistral(api_key=settings.mistral_api_key)
        response = await client.agents.complete_async(
            agent_id=settings.mistral_agent_id_interview,
            messages=messages,  # pyright: ignore  # pyright: ignore
        )
        
        assistant_text = _normalize_agent_content(response.choices[0].message.content)
        if not assistant_text:
            raise RuntimeError("Received empty interview response")
        
        # Simulate streaming by yielding text in chunks
        chunk_size = 15
        for i in range(0, len(assistant_text), chunk_size):
            chunk = assistant_text[i:i + chunk_size]
            yield chunk
            await asyncio.sleep(0.05)
        
        # Add to history
        history.append({"role": "user", "content": user_message.strip()})
        history.append({"role": "assistant", "content": assistant_text})


async def _run_extraction_in_background(
    session_id: str,
    interview_history: list[dict[str, str]],
    session_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Run profile extraction in background.
    Returns extraction result with profile and completeness.
    """
    try:
        # Build transcript for profile extraction
        transcript_history = [
            {"role": msg.get("role", ""), "content": msg.get("content", "")}
            for msg in interview_history
        ]
        
        # Extract profile
        profile_extractor = ProfileExtractorEngine()
        extraction_ctx = ExtractionContext(
            session_id=session_id,
            transcript_history=transcript_history,
            current_profile=UserProfile(**session_data["userProfile"]) if session_data.get("userProfile") else None,
        )
        
        extraction_result = await profile_extractor.extract(extraction_ctx)
        
        # Update session with extracted profile
        session_data["userProfile"] = extraction_result.extracted_profile.model_dump(mode="json")
        session_data["transcript"] = [
            {
                "id": f"te_{i:03d}",
                "turn": i + 1,
                "phase": "interview",
                "role": msg.get("role", "assistant"),
                "content": msg.get("content", ""),
                "timestamp": time.time(),
            }
            for i, msg in enumerate(interview_history)
        ]
        _save_session(session_id, session_data)
        
        return {
            "profile_completeness": extraction_result.profile_completeness,
            "extracted_fields": extraction_result.extracted_fields,
        }
    except Exception as exc:
        # Log the error but don't crash - extraction is secondary to streaming
        print(f"Background extraction error for {session_id}: {exc}")
        return {
            "profile_completeness": 0.0,
            "extracted_fields": {},
        }





# ---------------------------------------------------------------------------
# Router setup
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/interview", tags=["onboarding"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=dict[str, Any])
async def start_interview(request: InterviewStartRequest) -> dict[str, Any]:
    """
    Initialize interview session.
    
    Creates in-memory conversation session and initializes session.json
    if it doesn't exist.
    """
    settings = get_settings()
    session_path = _get_session_path(request.session_id)
    
    # Load or create session document
    if session_path.exists():
        session_data = _load_session(request.session_id)
        existing_profile = UserProfile(**session_data.get("userProfile", {})) if session_data.get("userProfile") else None
    else:
        # Create new session
        session_data = {
            "id": request.session_id,
            "status": "onboarding",
            "transcript": [],
            "userProfile": None,
            "currentSelf": None,
            "createdAt": time.time(),
            "updatedAt": time.time(),
        }
        existing_profile = None
    
    # Initialize interview session in memory
    interview_history = _initialize_interview_session(
        session_id=request.session_id,
        user_name=request.user_name,
        existing_profile=existing_profile,
    )
    
    # Save session data
    _save_session(request.session_id, session_data)
    
    # Return greeting
    greeting = interview_history[-1]["content"] if interview_history else "Hello!"
    
    return {
        "session_id": request.session_id,
        "agent_message": greeting,
        "profile_completeness": 0.0,
        "extracted_fields": {},
    }


@router.post("/reply", response_model=InterviewReplyResponse)
async def interview_reply(request: InterviewReplyRequest) -> InterviewReplyResponse:
    """
    Process user message through interview agent, extract profile.
    
    Flow:
    1. Get or create interview session
    2. Interview agent replies to user message
    3. Profile extraction runs on updated transcript
    4. Return response + profile update
    
    NOTE: For streaming responses, use /reply-stream endpoint instead.
    """
    # Get interview session (or create if first time)
    if request.session_id not in _INTERVIEW_HISTORIES:
        _initialize_interview_session(
            session_id=request.session_id,
            user_name="User",
            existing_profile=None,
        )

    interview_history = _INTERVIEW_HISTORIES[request.session_id]
    
    # Load current session data
    session_data = _load_session(request.session_id)
    
    # Get interview agent response
    try:
        agent_message = await _generate_interview_reply(interview_history, request.user_message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Interview agent error: {str(exc)}"
        )
    
    # Build transcript for profile extraction
    # (combine existing transcript + new user/agent turns)
    transcript_history = [
        {"role": msg.get("role", ""), "content": msg.get("content", "")}
        for msg in interview_history
    ]
    
    # Extract profile
    profile_extractor = ProfileExtractorEngine()
    extraction_ctx = ExtractionContext(
        session_id=request.session_id,
        transcript_history=transcript_history,
        current_profile=UserProfile(**session_data["userProfile"]) if session_data.get("userProfile") else None,
    )
    
    try:
        extraction_result = await profile_extractor.extract(extraction_ctx)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile extraction error: {str(exc)}"
        )

    agent_message = _apply_handoff_blocker(
        agent_message,
        extraction_result.profile_completeness,
        extraction_result.extracted_profile,
    )
    if interview_history and interview_history[-1].get("role") == "assistant":
        interview_history[-1]["content"] = agent_message
    
    # Update session with extracted profile
    session_data["userProfile"] = extraction_result.extracted_profile.model_dump(mode="json")
    session_data["transcript"] = [
        {
            "id": f"te_{i:03d}",
            "turn": i + 1,
            "phase": "interview",
            "role": msg.get("role", "assistant"),
            "content": msg.get("content", ""),
            "timestamp": time.time(),
        }
        for i, msg in enumerate(interview_history)
    ]
    _save_session(request.session_id, session_data)
    
    return InterviewReplyResponse(
        session_id=request.session_id,
        agent_message=agent_message,
        profile_completeness=extraction_result.profile_completeness,
        extracted_fields=extraction_result.extracted_fields,
    )


@router.post("/reply-stream")
async def interview_reply_stream(request: InterviewReplyRequest) -> StreamingResponse:
    """
    Process user message with STREAMING response (Server-Sent Events).
    
    This endpoint makes the interview feel responsive and reactive:
    - Streams agent response token-by-token as it arrives
    - Profile extraction runs in parallel without blocking
    - Updates sent as they complete (typically 1-3 seconds after message)
    - User sees typing effect while data is being processed
    
    Request:
        InterviewReplyRequest with session_id and user_message
    
    Response (Server-Sent Events):
        Streams JSON objects with types:
        - "chunk": Agent response text chunk
        - "extraction": Profile extraction results
        - "error": Error message
        - "done": Stream complete
    
    Example client code:
    ```javascript
    const response = await fetch('/interview/reply-stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id, user_message})
    });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        
        const text = decoder.decode(value, {stream: true});
        const lines = text.split('\\n');
        
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const json = JSON.parse(line.slice(6));
                if (json.type === 'chunk') {
                    // Append to display
                    display.append(json.data);
                } else if (json.type === 'extraction') {
                    // Update profile bar
                    updateProfile(json.data);
                }
            }
        }
    }
    ```
    """
    # Get interview session (or create if first time)
    if request.session_id not in _INTERVIEW_HISTORIES:
        _initialize_interview_session(
            session_id=request.session_id,
            user_name="User",
            existing_profile=None,
        )

    interview_history = _INTERVIEW_HISTORIES[request.session_id]
    
    # Load current session data
    session_data = _load_session(request.session_id)
    
    # Return streaming response with agent message and background extraction
    return StreamingResponse(
        _stream_response_with_extraction_v2(
            session_id=request.session_id,
            interview_history=interview_history,
            session_data=session_data,
            user_message=request.user_message,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _stream_response_with_extraction_v2(
    session_id: str,
    interview_history: list[dict[str, str]],
    session_data: dict[str, Any],
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Stream agent response chunks and extraction updates in parallel.
    Sends both response chunks and extraction results as they arrive.
    
    Sends:
    - {"type": "chunk", "data": "text chunk"} for agent message chunks
    - {"type": "extraction", "data": {...}} for extraction results
    """
    profile_before_dict = session_data.get("userProfile") or {}
    profile_before = UserProfile(**profile_before_dict) if profile_before_dict else None
    completeness_before = _calculate_completeness(profile_before) if profile_before else 0.0

    # For sessions already at 50%+, keep true token streaming.
    if completeness_before >= 0.5:
        extraction_task = asyncio.create_task(
            _run_extraction_in_background(session_id, interview_history, session_data)
        )

        try:
            async for chunk in _stream_interview_reply_with_chat_api(interview_history, user_message):
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'data': str(exc)})}\n\n"
            return

        try:
            extraction_result = await asyncio.wait_for(extraction_task, timeout=30.0)
            yield f"data: {json.dumps({'type': 'extraction', 'data': extraction_result})}\n\n"
        except asyncio.TimeoutError:
            print(f"Extraction timeout for {session_id}")
            yield f"data: {json.dumps({'type': 'extraction_timeout', 'data': {'message': 'Profile extraction is taking longer than expected'}})}\n\n"
        except Exception as exc:
            print(f"Extraction error for {session_id}: {exc}")
            yield f"data: {json.dumps({'type': 'extraction_error', 'data': str(exc)})}\n\n"

        yield "data: {\"type\": \"done\"}\n\n"
        return

    # For sessions below 50%, enforce handoff blocker before any chunk is emitted.
    try:
        agent_message = await _generate_interview_reply(interview_history, user_message)
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'data': str(exc)})}\n\n"
        return

    try:
        extraction_result = await asyncio.wait_for(
            _run_extraction_in_background(session_id, interview_history, session_data),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        print(f"Extraction timeout for {session_id}")
        extraction_result = {
            "profile_completeness": completeness_before,
            "extracted_fields": {},
        }
    except Exception as exc:
        print(f"Extraction error for {session_id}: {exc}")
        extraction_result = {
            "profile_completeness": completeness_before,
            "extracted_fields": {},
        }

    profile_after_dict = session_data.get("userProfile") or {}
    profile_after = UserProfile(**profile_after_dict) if profile_after_dict else None
    blocked_message = _apply_handoff_blocker(
        agent_message,
        extraction_result.get("profile_completeness", completeness_before),
        profile_after,
    )

    if blocked_message != agent_message:
        if interview_history and interview_history[-1].get("role") == "assistant":
            interview_history[-1]["content"] = blocked_message

        session_data["transcript"] = [
            {
                "id": f"te_{i:03d}",
                "turn": i + 1,
                "phase": "interview",
                "role": msg.get("role", "assistant"),
                "content": msg.get("content", ""),
                "timestamp": time.time(),
            }
            for i, msg in enumerate(interview_history)
        ]
        _save_session(session_id, session_data)

    chunk_size = 24
    for i in range(0, len(blocked_message), chunk_size):
        chunk = blocked_message[i:i + chunk_size]
        yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"

    yield f"data: {json.dumps({'type': 'extraction', 'data': extraction_result})}\n\n"
    yield "data: {\"type\": \"done\"}\n\n"


@router.get("/status", response_model=InterviewStatusResponse)
async def interview_status(session_id: str) -> InterviewStatusResponse:
    """Get current interview/profile status."""
    session_data = _load_session(session_id)
    
    profile_dict = session_data.get("userProfile", {})
    profile = UserProfile(**profile_dict) if profile_dict else None
    
    if not profile:
        return InterviewStatusResponse(
            session_id=session_id,
            profile_completeness=0.0,
            extracted_fields={},
            current_dilemma=None,
            is_ready_for_generation=False,
        )
    
    # Calculate completeness
    completeness = _calculate_completeness(profile)
    
    # Build extracted fields
    extracted_fields = _build_extracted_fields(profile)
    
    # Check readiness
    is_ready = _check_readiness(profile)
    
    return InterviewStatusResponse(
        session_id=session_id,
        profile_completeness=completeness,
        extracted_fields=extracted_fields,
        current_dilemma=profile.current_dilemma,
        is_ready_for_generation=is_ready,
    )


@router.post("/complete", response_model=InterviewCompleteResponse)
async def complete_interview(request: InterviewCompleteRequest) -> InterviewCompleteResponse:
    """
    Complete interview and generate CurrentSelf.
    
    Confirms dilemma (or uses extracted), generates CurrentSelf,
    then triggers future-self generation readiness.
    """
    session_data = _load_session(request.session_id)
    
    profile_dict = session_data.get("userProfile", {})
    if not profile_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user profile found. Complete interview first."
        )
    
    profile = UserProfile(**profile_dict)

    completeness = _calculate_completeness(profile)
    if completeness < 0.5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Profile completeness is below 50%. Continue onboarding with at least one "
                "more high-value answer before completing."
            ),
        )
    
    # Confirm or override dilemma
    if request.user_confirmed_dilemma:
        profile.current_dilemma = request.user_confirmed_dilemma
    
    # Generate CurrentSelf
    current_self_gen = CurrentSelfAutoGeneratorEngine()
    gen_ctx = CurrentSelfGenerationContext(
        session_id=request.session_id,
        user_profile=profile,
    )
    
    try:
        gen_result = await current_self_gen.generate(gen_ctx)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CurrentSelf generation error: {str(exc)}"
        )
    
    # Save to session
    session_data["userProfile"] = profile.model_dump(mode="json")
    session_data["currentSelf"] = gen_result.current_self.model_dump(mode="json")
    session_data["status"] = "ready_for_future_self_generation"
    
    # Initialize memory tree structure with root node
    _initialize_memory_tree(request.session_id, gen_result.current_self)
    
    _save_session(request.session_id, session_data)
    
    # Clear interview session from cache
    if request.session_id in _INTERVIEW_HISTORIES:
        del _INTERVIEW_HISTORIES[request.session_id]
    
    return InterviewCompleteResponse(
        session_id=request.session_id,
        user_profile=profile,
        current_self=gen_result.current_self,
        ready_for_future_generation=True,
        message="Onboarding complete! Ready to explore your future selves.",
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _calculate_completeness(profile: UserProfile) -> float:
    """Calculate profile completeness as 0-1."""
    total_fields = 20
    filled_fields = 0
    
    if profile.core_values:
        filled_fields += 1
    if profile.fears:
        filled_fields += 1
    if profile.hidden_tensions:
        filled_fields += 1
    if profile.decision_style:
        filled_fields += 1
    if profile.self_narrative:
        filled_fields += 1
    if profile.current_dilemma:
        filled_fields += 1
    if profile.career.job_title:
        filled_fields += 1
    if profile.career.career_goal:
        filled_fields += 1
    if profile.financial.income_level:
        filled_fields += 1
    if profile.financial.money_mindset:
        filled_fields += 1
    if profile.personal.relationships:
        filled_fields += 1
    if profile.personal.hobbies:
        filled_fields += 1
    if profile.personal.personal_values:
        filled_fields += 1
    if profile.health.mental_health:
        filled_fields += 1
    if profile.health.physical_health:
        filled_fields += 1
    if profile.life_situation.current_location:
        filled_fields += 1
    if profile.life_situation.life_stage:
        filled_fields += 1
    
    return min(1.0, filled_fields / total_fields)


def _build_extracted_fields(profile: UserProfile) -> dict[str, bool]:
    """Build extracted_fields dict for UI."""
    return {
        "core_values": bool(profile.core_values),
        "fears": bool(profile.fears),
        "hidden_tensions": bool(profile.hidden_tensions),
        "decision_style": bool(profile.decision_style),
        "self_narrative": bool(profile.self_narrative),
        "current_dilemma": bool(profile.current_dilemma),
        "job_title": bool(profile.career.job_title),
        "career_goal": bool(profile.career.career_goal),
        "income_level": bool(profile.financial.income_level),
        "money_mindset": bool(profile.financial.money_mindset),
        "relationships": bool(profile.personal.relationships),
        "hobbies": bool(profile.personal.hobbies),
        "life_stage": bool(profile.life_situation.life_stage),
    }


def _check_readiness(profile: UserProfile) -> bool:
    """Check if profile is ready for CurrentSelf generation."""
    has_dilemma = bool(profile.current_dilemma and len(str(profile.current_dilemma)) > 10)
    has_psychology = bool(profile.core_values) and bool(profile.fears)
    has_narrative = bool(profile.self_narrative) or bool(
        profile.decision_style and profile.hidden_tensions
    )
    return bool(has_dilemma and has_psychology and has_narrative)
