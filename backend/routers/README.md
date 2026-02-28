# Routers — FastAPI Route Definitions

## Purpose
Thin routing layer that maps HTTP/WebSocket endpoints to engine calls. Routers handle request validation, session lookup, and response formatting — but contain no business logic. All AI logic lives in `engines/`.

## Files

### `interview.py`
- `POST /interview/respond` — accepts user message + session ID, calls InterviewAgent, returns next question
- `POST /interview/complete` — signals interview is done, returns confirmation

### `profile.py`
- `POST /profile/build` — accepts session ID (which has the transcript), calls ProfileBuilder, returns UserProfile + CurrentSelf card

### `future_self.py`
- `POST /future-self/generate` — accepts session ID, calls FutureSelfGenerator, returns list of SelfCards
- `POST /future-self/select` — accepts session ID + selected self ID, locks it in for conversation

### `conversation.py`
- `WS /conversation/stream` — WebSocket endpoint for real-time voice conversation. Receives audio chunks, returns audio + subtitle text
- `POST /conversation/summarize` — ends conversation, calls summary generation, returns debrief data
- `POST /conversation/backtrack` — switch to a different future self branch. Commits current memory, checks out target branch, returns updated session state

### `avatar.py`
- `POST /avatar/generate` — accepts a SelfCard, calls AvatarGenerator (Mistral Pixtral / Gemini), returns generated image URL. Caches result in session storage

## Interaction Pattern
```
Frontend Request → Router (validate + extract) → Engine (AI logic) → Router (format response) → Frontend
```

## TODO
- [ ] Create interview router with respond and complete endpoints
- [ ] Create profile router with build endpoint
- [ ] Create future_self router with generate and select endpoints
- [ ] Create conversation router with WebSocket stream, summarize, and backtrack
- [ ] Create avatar router with generate endpoint
- [ ] Add session middleware for session ID management
- [ ] Add request/response Pydantic models for validation
