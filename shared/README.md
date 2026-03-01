# Shared Contracts

Shared data-contract layer between frontend and backend.

## Why
Prevents schema drift across layers (field names, required fields, enum values).

## Contract Areas
- Session identifiers and state flags
- Profile payloads
- Self card payloads (`current`/`future`)
- Conversation payloads/history
- Pipeline status and branching responses

## Rules
- One canonical shape per payload type
- Keep naming/casing explicit and documented
- Update both backend and frontend together when contracts change