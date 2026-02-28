# Backend — Python / FastAPI

## Purpose
The API server that powers all AI logic: interview orchestration, profile extraction, future self generation, and real-time voice conversation. Handles the handoff between Mistral (LLM) and ElevenLabs (voice synthesis).

## Tech Stack
- **Framework**: FastAPI (async, WebSocket support, auto-docs)
- **Language**: Python 3.11+ with type hints
- **LLM**: Mistral API (interview logic, profile building, future self persona, conversation)
- **Voice (full pipeline)**: ElevenLabs API (both STT and TTS, streaming)
- **Avatar Generation**: Mistral Pixtral or Google Gemini (AI image generation for persona avatars)
- **Server**: Uvicorn with WebSocket support

## Why Python (not Node)
- Mistral and ElevenLabs SDKs are Python-first
- Profile extraction and prompt engineering are more natural in Python
- FastAPI gives us async + WebSockets + auto-generated API docs
- OOP class structure maps cleanly to the agent/engine pattern

## API Endpoints

### REST
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/interview/respond` | Send user message, get interviewer's next question |
| POST | `/interview/complete` | Signal interview is done, trigger profile build |
| POST | `/profile/build` | Extract structured profile from interview transcript |
| POST | `/future-self/generate` | Generate future self options from profile + dilemma |
| POST | `/future-self/select` | Lock in the selected future self for conversation |
| POST | `/conversation/summarize` | Generate debrief summary after conversation ends |
| POST | `/avatar/generate` | Generate avatar image for a SelfCard via Mistral Pixtral / Gemini |

### WebSocket
| Endpoint | Purpose |
|----------|---------|
| `ws://*/conversation/stream` | Real-time voice conversation (audio in → text + audio out) |

## Interaction with Frontend
- REST endpoints return JSON matching the shared data contracts (see `shared/`)
- WebSocket streams bidirectional audio + text for the conversation chamber
- All responses include latency-conscious design: streaming where possible

## Interaction with Other Modules
- Uses prompt templates from `prompts/`
- Uses data models/schemas from `shared/`
- Interview agent, profile builder, self generator, and conversation engine are separate classes in `backend/engines/`

## TODO
- [ ] Initialize FastAPI project with uvicorn
- [ ] Set up project structure (routers, engines, models, config)
- [ ] Create InterviewAgent class with Mistral integration
- [ ] Create ProfileBuilder class (transcript → structured profile)
- [ ] Create FutureSelfGenerator class (profile → persona cards)
- [ ] Create ConversationEngine class with memory management
- [ ] Create VoicePipeline class (ElevenLabs STT + TTS, fully ElevenLabs)
- [ ] Create AvatarGenerator class (Mistral Pixtral / Gemini image generation)
- [ ] Wire up REST endpoints to engines
- [ ] Wire up WebSocket endpoint for real-time conversation
- [ ] Add environment config (.env for API keys)
- [ ] Add error handling and request validation
- [ ] Set up CORS for frontend origin
