# Routers

Routers expose API boundaries and delegate domain logic to engines.

## Files
- `onboarding.py`: interview lifecycle and onboarding completion
- `pipeline.py`: onboarding handoff, exploration start, branching, status
- `future_self.py`: future-self generation at root and deeper levels
- `conversation.py`: text/streaming replies and transcript persistence

## Design Rules
- Keep router logic thin (validation, HTTP semantics, error mapping)
- Keep business logic in engines
- Keep request/response shapes aligned with shared schemas