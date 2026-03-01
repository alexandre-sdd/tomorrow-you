# Agent Infrastructure

High-level map of backend components and provider boundaries.

## Runtime Layers
- **Routers**: HTTP/WebSocket entrypoints
- **Engines**: orchestration + generation + context logic
- **Storage**: session state, transcripts, memory nodes/branches
- **Providers**: Mistral (LLM), ElevenLabs (voice), optional Gemini (avatar)

## Request Paths
- Onboarding: interview routes → extraction/current-self generation → session update
- Exploration: pipeline start → future generation → memory tree update
- Branching: conversation + transcript insights → child future generation

## Integration Notes
- Provider calls are isolated in engine/client wrappers
- Router responses use shared schema conventions
- Tree/transcript writes are append-oriented and session-scoped