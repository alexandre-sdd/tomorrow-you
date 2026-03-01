# Conversation Engine MVP

Minimal terminal-compatible conversation loop for a selected future-self branch.

## Goal
Support fast text conversation with branch context and transcript persistence.

## Flow
1. Resolve branch context from selected `self_id`
2. Compose prompt with ancestor + transcript context
3. Generate reply via Mistral client (sync or streaming)
4. Append user/assistant turns to transcript

## Commands
Start chat against an existing session/self:

```bash
python3 -m backend.cli.chat_future_self \
  --session-id <session_id> \
  --self-id <self_id>
```

Generate futures first if needed:

```bash
python3 -m backend.cli.generate_future_selves \
  --session-id <session_id> \
  --count 2
```