# Models

Pydantic models define API contracts and persisted data structures.

## Main Categories
- Session and onboarding payloads
- Profile sections (career, financial, personal, health, life situation)
- Self cards (`current` and `future`)
- Conversation request/response/history messages
- Pipeline status and branching payloads

## Conventions
- CamelCase aliases at API boundaries when required
- Strict required fields for core runtime values
- Optional fields for progressive profile enrichment