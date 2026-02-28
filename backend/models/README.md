# Models — Pydantic Data Models

## Purpose
Python Pydantic models that match the shared data contracts. Used for request/response validation in FastAPI routes and as internal data structures passed between engines.

## Files

### `user_profile.py`
```python
class UserProfile(BaseModel):
    id: str
    core_values: list[str]
    fears: list[str]
    hidden_tensions: list[str]
    decision_style: str
    self_narrative: str
    current_dilemma: str
```

### `self_card.py`
```python
class VisualStyle(BaseModel):
    primary_color: str
    accent_color: str
    mood: str
    glow_intensity: float  # 0.0 - 1.0

class SelfCard(BaseModel):
    id: str
    type: Literal["current", "future"]
    name: str
    optimization_goal: str
    tone_of_voice: str
    worldview: str
    core_belief: str
    trade_off: str
    avatar_prompt: str                # description for AI image generation
    avatar_url: str | None = None     # path/URL to generated image
    visual_style: VisualStyle
    voice_id: str
```

### `message.py`
```python
class Message(BaseModel):
    id: str
    role: Literal["user", "interviewer", "future_self"]
    content: str
    timestamp: float
```

### `memory.py`
```python
class MemoryNode(BaseModel):
    id: str
    parent_id: str | None = None
    branch_label: str
    facts: list[KeyFact]
    notes: list[str]
    self_card: SelfCard | None = None
    created_at: float

class MemoryBranch(BaseModel):
    name: str
    head_node_id: str
    parent_branch_name: str | None = None
```

### `transcript.py`
```python
class TranscriptEntry(BaseModel):
    id: str
    turn: int
    phase: Literal["interview", "conversation", "backtrack", "selection"]
    role: Literal["user", "interviewer", "future_self", "system"]
    self_name: str | None = None
    content: str
    timestamp: float
```

### `session.py`
```python
class Session(BaseModel):
    id: str
    status: Literal["interview", "profile", "selection", "conversation", "debrief"]
    transcript: list[TranscriptEntry]   # linear, append-only
    user_profile: UserProfile | None
    current_self: SelfCard | None
    future_self_options: list[SelfCard]
    selected_future_self: SelfCard | None
    memory_head: str                    # current branch name (like git HEAD)
    memory_branches: list[MemoryBranch]
    memory_nodes: list[MemoryNode]
    created_at: float
    updated_at: float
```

### `key_fact.py`
```python
class KeyFact(BaseModel):
    id: str
    fact: str
    source: Literal["interview", "conversation"]
    extracted_at: float
```

## Naming Convention
- Python models use `snake_case` (Pydantic convention)
- JSON serialization uses `camelCase` via Pydantic `alias_generator`
- This means the API sends/receives camelCase JSON but Python code uses snake_case

## TODO
- [ ] Create all Pydantic models with proper types and validators
- [ ] Add MemoryNode, MemoryBranch, and TranscriptEntry models
- [ ] Configure camelCase alias generation for JSON compatibility
- [ ] Add example/factory methods for testing
- [ ] Ensure models match shared schemas exactly
