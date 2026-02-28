# Multi-Level Future Self Branching Implementation

## Overview

This system enables **tree-based exploration** of future selves, allowing users to:
1. Generate initial choices (Level 1: NYC vs Singapore)  
2. Explore how each choice evolved differently (Level 2: outcomes based on life factors)
3. Navigate back and forth without losing data
4. Build a complete decision tree over multiple sessions

## Architecture

### Tree Structure

```
root (Current Self)
├─ Self Who Took the Singapore Move (Level 1)
│  ├─ Self Who Took Singapore and Found Unexpected Community (Level 2)
│  └─ Self Who Took Singapore and Experienced Career Burnout (Level 2)
└─ Self Who Stayed in New York (Level 1)
   ├─ Self Who Stayed in NYC and Started Own Business (Level 2)
   └─ Self Who Stayed in NYC and Family Expanded (Level 2)
```

### Data Storage

**Session Structure:**
```json
{
  "futureSelfOptions": [...],           // Backward compat (root level only)
  "futureSelvesFull": {                 // ALL selves by ID (tree)
    "self_id_1": { ...selfCard... },
    "self_id_2": { ...selfCard... }
  },
  "explorationPaths": {                 // Tracks what's been explored
    "root": ["self_id_1", "self_id_2"],
    "self_id_1": ["self_id_3", "self_id_4"]
  }
}
```

**SelfCard Fields:**
- `parent_self_id`: ID of parent (None for root level)
- `depth_level`: 1 for initial choice, 2+ for secondary
- `children_ids`: IDs of generated child selves

## Key Features

### 1. Root Level Generation
```python
POST /future-self/generate
{
  "sessionId": "user_001",
  "count": 2,
  "parentSelfId": null  # Root level
}
```
- Generates initial choices from current dilemma
- Uses original prompt template
- Links to root memory node

### 2. Secondary Level Generation
```python
POST /future-self/generate
{
  "sessionId": "user_001",
  "count": 2,
  "parentSelfId": "self_future_singapore_001"
}
```
- Generates outcome variations from chosen path
- Uses secondary prompt template (explores consequences)
- Links to parent self's memory node

### 3. Tree Navigation Endpoints

**Get Full Tree:**
```python
GET /future-self/{session_id}/tree
```
Returns:
- `allSelves`: All generated selves by ID
- `explorationPaths`: Parent → children mapping
- `rootOptions`: Level 1 choices (backward compat)

**Get Children:**
```python
GET /future-self/{session_id}/self/{self_id}/children
```
Returns list of secondary selves generated from parent

## Implementation Details

### 1. Schema Updates (`backend/models/schemas.py`)

Added to `SelfCard`:
```python
parent_self_id: str | None = None
depth_level: int = 1
children_ids: list[str] = []
```

Added to `GenerateFutureSelvesRequest`:
```python
parent_self_id: str | None = None
```

### 2. Generator Engine (`backend/engines/future_self_generator.py`)

**New Template:** `_SECONDARY_MESSAGE_TEMPLATE`
- Context: Person chose X, 2-3 years later
- Focus: How same choice evolved differently
- Factors: Relationships, career, trade-offs, external events

**New Method:** `generate_secondary()`
- Takes parent_self and user_profile
- Sets parent_self_id and depth_level on children
- Returns list of secondary SelfCards

### 3. Router Logic (`backend/routers/future_self.py`)

**Branch Detection:**
```python
if request.parent_self_id is None:
    # Root generation
    parent_node_id = _find_root_node_id(...)
    parent_branch_name = "root"
else:
    # Secondary generation
    parent_self = load from futureSelvesFull
    parent_node_id = _find_node_id_for_self(...)
    parent_branch_name = parent_self.name
```

**Tree Preservation:**
```python
# Add to full tree
session_data["futureSelvesFull"][self_card.id] = self_card

# Track exploration
session_data["explorationPaths"][parent_key].append(self_id)

# Update parent's children
parent_data["childrenIds"].append(child_ids)
```

### 4. Memory Branch Linking

Updated `_create_memory_branches()`:
- Accepts `parent_node_id` and `parent_branch_name`
- Links new nodes to parent (not always root)
- Maintains branch hierarchy in branches.json

## Prompt Engineering

### Secondary Generation Prompt

**Key Directives:**
- ✅ Explore how SAME initial choice evolved differently
- ✅ Focus on life factors (relationships, opportunities, trade-offs)
- ✅ Names: "Self Who [parent choice] and [what happened]"
- ✅ Don't rehash original dilemma
- ✅ Visual mood reflects emotional outcome (not copy parent)

**Example Names:**
- "Self Who Took the Singapore Move and Found Unexpected Community"
- "Self Who Took the Singapore Move and Experienced Career Burnout"
- "Self Who Stayed in NYC and Started Own Business"
- "Self Who Stayed in NYC and Family Expanded"

## Testing

Run comprehensive test:
```bash
$env:PYTHONPATH="$PWD"; python backend/test_multilevel_branching.py
```

**Test validates:**
- ✓ Root level generation
- ✓ Secondary generation from first choice
- ✓ Navigation back to generate from second choice
- ✓ All 6 selves preserved in futureSelvesFull
- ✓ Exploration paths tracked correctly
- ✓ Parent-child links established
- ✓ Memory nodes correctly linked
- ✓ Branch structure maintains hierarchy

## Usage Example

```python
# 1. Generate root level
response = await generate_future_selves(
    GenerateFutureSelvesRequest(
        session_id="user_001",
        count=2,
        parent_self_id=None
    )
)
# Returns: Singapore Move, Stay in NYC

# 2. Explore Singapore outcome
singapore_id = response.future_self_options[0].id
response2 = await generate_future_selves(
    GenerateFutureSelvesRequest(
        session_id="user_001",
        count=2,
        parent_self_id=singapore_id
    )
)
# Returns: Found Community, Career Burnout

# 3. Go back and explore NYC outcome
nyc_id = response.future_self_options[1].id
response3 = await generate_future_selves(
    GenerateFutureSelvesRequest(
        session_id="user_001",
        count=2,
        parent_self_id=nyc_id
    )
)
# Returns: Started Business, Family Expanded

# 4. All 6 selves preserved in session.futureSelvesFull
# Can navigate tree using /tree and /children endpoints
```

## Benefits

1. **No Data Loss**: All generated selves stored in `futureSelvesFull`
2. **Full Navigation**: Can explore any branch without losing others
3. **Tree Structure**: Maintains parent-child relationships
4. **Backward Compatible**: `futureSelfOptions` still works for simple cases
5. **Scalable**: Supports up to 5 depth levels (configurable)
6. **Memory Coherence**: Branch nodes correctly linked in memory system

## Future Enhancements

1. **Depth Limits**: Enforce max depth per session
2. **Branch Pruning**: Allow removing unwanted branches
3. **Path Comparison**: Compare different paths side-by-side
4. **Conversation Context**: Use parent conversations in secondary generation
5. **Visual Tree UI**: Frontend tree visualization with navigation

## Files Modified

1. `backend/models/schemas.py` - Added tree navigation fields
2. `backend/engines/future_self_generator.py` - Added secondary generation
3. `backend/routers/future_self.py` - Added tree logic and navigation endpoints
4. `.gitignore` - Exclude test_sessions/

## Files Created

1. `backend/test_multilevel_branching.py` - Comprehensive test
2. `MULTI_LEVEL_BRANCHING.md` - This documentation
