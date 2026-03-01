# Prompts

Version-controlled prompt files used by backend engines and agents.

## Purpose
- Keep prompt logic separate from code
- Make edits reviewable and diff-friendly
- Support fast prompt iteration without router/engine rewrites

## Prompt Files
- `interview_agent.md`
- `profile_extraction.md`
- `future_self_generation.md`

## Usage
Engines load prompts, inject runtime context, then call model/provider clients.