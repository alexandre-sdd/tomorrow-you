# ConversationEngine MVP (CLI + Memory Persistence)

## Goal
Run a fast, natural text conversation in the terminal with a selected future-self branch using Mistral.

## In Scope (this phase)
1. Read-only context resolution from session storage.
2. Prompt composition for branch-grounded persona conversation.
3. In-memory conversation session state.
4. Mistral API client wrapper with sync + streaming methods.
5. CLI REPL loop for terminal-only conversations.
6. Persist conversation transcript per turn.
7. Extract key memory signals from transcript at checkpoint events (exit/rebranch).

## Out of Scope (later)
1. Voice pipeline integration.
2. Advanced retry/backoff strategy.

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
- `/branch [2|3] [optional time horizon]` generates children from current self and lets the user pick a path.
- `/branch-reprompt [2|3] [optional time horizon]` branches and automatically re-asks the latest user prompt on the selected path.
- `/reprompt` re-sends the last user message on the current path.
- `/exit` exits the chat session.

## Performance Constraints
- Keep system prompt compact.
- Limit injected memory facts/notes.
- Limit rolling history window.
- Stream model output for fast first-token UX.

## Data Safety
- Writes are limited to session-local memory artifacts:
  - append turn data to `transcript.json`
  - recompute/replace extracted transcript insights on current branch memory node (`facts`/`notes`)
- No destructive edits and no branch history pruning.

## Transcript Insight Policy
- Transcript extraction is role-configurable; default input roles are `user` + `assistant`.
- Rebranch ancestor excerpts are role-configurable; default included roles are `user`, `assistant`, `memory`.
- Each extraction run for a branch removes prior auto-extracted transcript insights and writes a fresh set.

## Quick Run
```bash
python3 -m backend.cli.chat_future_self \
  --session-id user_nyc_singapore_001 \
  --self-id self_future_nyc_001
```

If `MISTRAL_API_KEY` is not set in your shell, pass `--api-key <key>`.

You can also generate a new batch first:
```bash
python3 -m backend.cli.generate_future_selves \
  --session-id user_nyc_singapore_001 \
  --count 2
```

Backfill transcript insights for an existing session:
```bash
python3 -m backend.cli.backfill_transcript_insights \
  --session-id user_nyc_singapore_001
```
