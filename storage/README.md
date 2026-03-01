# Storage

File-backed session storage for local development and testing.

## Session Layout
Each session directory typically contains:
- `session.json` (session state and profile/self data)
- `transcript.json` (conversation and system events)
- `memory/` (branch/node artifacts when branching is used)

## Behavior
- Session-scoped writes
- Append-style transcript updates
- Memory tree artifacts for branch exploration

## Notes
- Designed for deterministic local debugging
- Production deployments can replace this layer with persistent storage