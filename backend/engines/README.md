# Engines

Engines contain business logic behind API routes.

## Core Engines
- `pipeline_orchestrator.py`: end-to-end workflow sequencing
- `future_self_generator.py`: persona generation
- `profile_extractor.py`: structured profile extraction
- `current_self_auto_generator.py`: current-self card generation
- `conversation_session.py`: branch-level conversation handling
- `conversation_memory.py`: transcript insight extraction/persistence
- `context_resolver.py`: ancestor/context retrieval for branching
- `prompt_composer.py`: final prompt assembly
- `mistral_client.py`: chat client wrapper
- `tree_visualizer.py`: textual tree output

## Principles
- Stateless where possible
- Schema-first boundaries
- Best-effort persistence for non-critical side effects
- Explicit error classes for orchestration/state errors