# ConversationEngine MVP (CLI, No Storage Writes)

## Goal
Run a fast, natural text conversation in the terminal with a selected future-self branch using Mistral.

## In Scope (this phase)
1. Read-only context resolution from session storage.
2. Prompt composition for branch-grounded persona conversation.
3. In-memory conversation session state (no persistence).
4. Mistral API client wrapper with sync + streaming methods.
5. CLI REPL loop for terminal-only conversations.

## Out of Scope (later)
1. Voice pipeline integration.
2. Memory extraction/commit writes.
3. Advanced retry/backoff strategy.

## Inputs
- `session_id` (example: `user_nyc_singapore_001`)
- `branch_name` (example: `self-who-stayed-in-new-york`)
- `storage_root` (default: `storage/sessions`)

## Read Path
1. Load `storage/sessions/{session_id}/session.json`.
2. Load branch refs from `memory/branches.json` (fallback: `session.memoryBranches`).
3. Load memory nodes from `memory/nodes/*.json` (fallback: `session.memoryNodes`).
4. Resolve the branch head node and walk parent links to root.
5. Build conversation context:
- `userProfile`
- branch `selfCard`
- merged facts/notes from root -> head path
- compact profile summary string

## Prompting Rules
- Persona is always the selected future self.
- Responses should feel human and natural, not robotic.
- Stay consistent with optimization goal, worldview, and trade-off.
- Use branch facts as grounding context.
- Keep responses concise by default for latency and turn speed.

## CLI Commands
- `/context` prints active persona and branch context.
- `/reset` clears in-memory turn history.
- `/exit` exits the chat session.

## Performance Constraints
- Keep system prompt compact.
- Limit injected memory facts/notes.
- Limit rolling history window.
- Stream model output for fast first-token UX.

## Data Safety
- Read-only mode for MVP.
- No writes to `session.json`, `transcript.json`, or memory nodes.

## Quick Run
```bash
python3 -m backend.cli.chat_future_self \
  --session-id user_nyc_singapore_001 \
  --branch self-who-stayed-in-new-york
```

If `MISTRAL_API_KEY` is not set in your shell, pass `--api-key <key>`.
