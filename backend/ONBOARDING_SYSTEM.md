# Onboarding System Implementation

## Overview

The Tomorrow You onboarding system is a two-agent, hybrid-flow design that creates a fluid conversational experience while progressively building a rich user profile. It culminates in auto-generating a *CurrentSelf* persona card, which triggers the system's future-self branching and exploration engine.

### System Flow

```
┌─────────────────────────────────────────────────────────────┐
│  POST /interview/start                                      │
│  Initialize interview session (in-memory conversation)      │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  POST /interview/reply (repeated)                           │
│  1. Interview Agent replies to user message                 │
│  2. Profile Extraction Agent parses transcript              │
│  3. Return response + profile update                        │
│  4. UI shows profile completeness (0-100%)                  │
└────────┬────────────────────────────────────────────────────┘
         │ (Multiple exchanges)
         ▼
┌─────────────────────────────────────────────────────────────┐
│  GET /interview/status                                      │
│  Check profile completeness and readiness                   │
│  When dilemma_confidence >= 0.8 → Ready                     │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  POST /interview/complete                                   │
│  1. Confirm dilemma (or use extracted)                      │
│  2. CurrentSelfAutoGenerator creates CurrentSelf persona    │
│  3. Save to session.json                                    │
│  4. Return ready signal                                     │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  POST /future-self/generate (existing system)               │
│  Generate 2-3 contrasting futures from the dilemma          │
│  User selects one future → Starts conversation              │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Interview Agent

**Location**: Managed in-memory via `backend/routers/onboarding.py`

**System Prompt**: [prompts/interview_agent.md](../prompts/interview_agent.md)

**Responsibilities**:
- Natural, flowing conversation that guides users through 6 life dimensions
- Ask follow-up questions, adapt based on responses
- Steer naturally toward the central dilemma
- No mechanical checklists; feel human

**Key Principles**:
- Warm and curious, not clinical
- Weave topics together (don't jump mechanically)
- Surface contradictions gently
- Build toward dilemma as natural conclusion

**Session Management**:
- Runs as `BranchConversationSession` in memory
- Uses `PromptComposer` to inject system prompt + conversation history
- Messages sent to Mistral API directly (no agent ID needed—uses model)

---

### 2. Profile Extraction Engine

**Location**: `backend/engines/profile_extractor.py`

**System Prompt**: [prompts/profile_extraction.md](../prompts/profile_extraction.md)

**Responsibilities**:
- Parse interview transcript after each user message
- Extract structured data into 6 profile dimensions
- Rate confidence (0-1) for each piece of data
- Merge new extractions with existing profile (don't overwrite)
- Surface contradictions in `hidden_tensions`
- Track readiness for CurrentSelf generation

**Profile Dimensions**:
1. **Life Situation** - location, life stage, responsibilities, transitions
2. **Relationships & Personal** - relationships, interests, values, hobbies
3. **Career & Work** - job, industry, experience, goals, satisfaction
4. **Financial** - income, goals, mindset, risk tolerance
5. **Health & Wellbeing** - physical, mental, sleep, stress, goals
6. **Psychology** - core values, fears, hidden tensions, decision style

**Confidence Tracking**:
```python
0.0      = Not mentioned / completely unclear
0.2-0.3  = Vague reference or inference
0.5      = Stated but with user uncertainty
0.7-0.8  = Explicitly stated, somewhat detailed
0.9-1.0  = Explicit, detailed, unambiguous
```

**Integration with Mistral**:
- Uses `mistral_agent_id_profile_extraction` agent (create on console.mistral.ai)
- Enforces JSON schema via Mistral's `response_format` parameter
- System prompt loaded from `prompts/profile_extraction.md`

---

### 3. CurrentSelf Auto-Generator

**Location**: `backend/engines/current_self_auto_generator.py`

**Responsibilities**:
- Takes a completed UserProfile
- Auto-generates a CurrentSelf `SelfCard` representing the user *now*
- Derives: optimization goal, tone, worldview, core belief, trade-off
- Generates detailed avatar prompt
- Selects visual style (colors, mood, glow)
- Assigns ElevenLabs voice by mood

**Key Insight**:
CurrentSelf is the *grounded perspective* from which the user views their dilemma. It's analytical yet emotionally grounded, reflecting their present contradictions and tensions.

**Integration with Mistral**:
- Uses `mistral_agent_id_current_self_generation` agent
- Enforces JSON schema via `response_format`
- System prompt embedded in engine (derived from profile context)

**Voice Assignment**:
```python
mood → ElevenLabs voice_id (from settings.elevenlabs_voice_pool)
e.g., "calm" → "MF3mGyEYCl7XYWbV9V6O"
```

---

## Data Models

### Extended UserProfile

```python
class UserProfile(BaseModel):
    id: str
    core_values: list[str]
    fears: list[str]
    hidden_tensions: list[str]
    decision_style: str
    self_narrative: str
    current_dilemma: str
    
    # NEW: Extended profile sections
    career: CareerProfile
    financial: FinancialProfile
    personal: PersonalProfile
    health: HealthProfile
    life_situation: LifeSituationProfile
```

### Sub-profiles

Each sub-profile captures specific dimensions:

```python
CareerProfile = {
    job_title, industry, seniority_level, years_experience,
    current_company, career_goal, job_satisfaction, main_challenges
}

FinancialProfile = {
    income_level, financial_goals, money_mindset,
    risk_tolerance, main_financial_concern
}

PersonalProfile = {
    hobbies, daily_routines, main_interests, relationships,
    key_relationships, personal_values
}

HealthProfile = {
    physical_health, mental_health, sleep_quality,
    exercise_frequency, stress_level, health_goals
}

LifeSituationProfile = {
    current_location, life_stage, major_responsibilities,
    recent_transitions, upcoming_changes
}
```

### Extraction Output

```python
class ExtractedProfileData(BaseModel):
    # Each dimension with confidence score
    career: CareerProfile
    career_confidence: float  # 0-1
    
    financial: FinancialProfile
    financial_confidence: float  # 0-1
    
    # ... similar for other dimensions
    
    # Overall readiness
    current_dilemma: str
    dilemma_confidence: float
```

---

## API Endpoints

### POST /interview/start

Initialize interview session.

**Request**:
```json
{
  "session_id": "user_nyc_001",
  "user_name": "Alex"
}
```

**Response**:
```json
{
  "session_id": "user_nyc_001",
  "agent_message": "Hello Alex! I'm here to get to know you...",
  "profile_completeness": 0.0,
  "extracted_fields": {}
}
```

---

### POST /interview/reply

Send user message, get interview response + profile update.

**Request**:
```json
{
  "session_id": "user_nyc_001",
  "user_message": "I work in tech, VP of Product at a startup"
}
```

**Response**:
```json
{
  "session_id": "user_nyc_001",
  "agent_message": "That's a great role! What drew you to VP-level work...",
  "profile_completeness": 0.25,
  "extracted_fields": {
    "job_title": true,
    "career_goal": false,
    "income_level": false,
    ...
  }
}
```

---

### GET /interview/status

Check profile completeness and readiness.

**Query Parameters**:
- `session_id` (required): Session ID

**Response**:
```json
{
  "session_id": "user_nyc_001",
  "profile_completeness": 0.65,
  "extracted_fields": { ... },
  "current_dilemma": "Should I relocate to Singapore for a VP promotion?",
  "is_ready_for_generation": true
}
```

---

### POST /interview/complete

Generate CurrentSelf and signal readiness for future-self generation.

**Request**:
```json
{
  "session_id": "user_nyc_001",
  "user_confirmed_dilemma": null  // or override with custom dilemma
}
```

**Response**:
```json
{
  "session_id": "user_nyc_001",
  "user_profile": { ... },  // Full UserProfile object
  "current_self": { ... },  // Generated SelfCard
  "ready_for_future_generation": true,
  "message": "Onboarding complete! Ready to explore future selves."
}
```

**Side Effects**:
- Saves `userProfile` + `currentSelf` to `session.json`
- Sets session status to `"ready_for_future_self_generation"`
- Clears interview session from memory cache

---

## Session Persistence

### Session JSON Structure

```json
{
  "id": "user_nyc_001",
  "status": "onboarding" | "ready_for_future_self_generation" | "selection" | "conversation",
  
  "transcript": [
    { "id": "te_001", "turn": 1, "phase": "interview", "role": "user", "content": "...", "timestamp": ... },
    { "id": "te_002", "turn": 2, "phase": "interview", "role": "assistant", "content": "...", "timestamp": ... },
    ...
  ],
  
  "userProfile": { ... },       // Extended UserProfile with all sub-profiles
  "currentSelf": { ... },        // Generated SelfCard (type: "current")
  
  "futureSelfOptions": [ ... ], // Generated after /future-self/generate
  "selectedFutureSelf": null,   // Set when user selects one
  
  // ... other existing fields (memory, branches, etc.)
  
  "createdAt": 1234567890,
  "updatedAt": 1234567890
}
```

---

## Hybrid Flow Rationale

### Why Hybrid (Incremental + Progressive)?

1. **Incremental**: Profile updates after *each* user message
   - Enables UI feedback ("Profile 65% complete")
   - Early detection of missing data categories
   - Allows "nudging" toward specific topics if gaps remain

2. **Progressive**: Profile extraction refines across interview
   - Early confidence scores improve as data emerges
   - Contradictions surface naturally
   - Dilemma crystallizes toward the end

3. **Natural Conversation**: Interview agent steers toward completeness without awareness of extraction
   - No hard skip-ahead logic
   - No "we need to cover X before moving on"
   - Follows user's energy and flow

---

## Setup & Configuration

### 1. Create Mistral Agents

Go to [console.mistral.ai/agents](https://console.mistral.ai/agents) and create 3 agents:

#### Agent 1: Interview Agent
- **Name**: "Tomorrow You Interview"
- **System Prompt**: Copy entire contents of `prompts/interview_agent.md`
- **Note**: Copy the agent ID (format: `ag:xxxx`)

#### Agent 2: Profile Extraction
- **Name**: "Tomorrow You Profile Extraction"
- **System Prompt**: Copy entire contents of `prompts/profile_extraction.md`
- **Note**: Copy the agent ID

#### Agent 3: CurrentSelf Generation
- **Name**: "Tomorrow You CurrentSelf Generation"
- **System Prompt**: Use the embedded prompt in `backend/engines/current_self_auto_generator.py` (or create a simplified version in prompts/)
- **Note**: Copy the agent ID

### 2. Update .env

```bash
# Add to .env:
MISTRAL_AGENT_ID_FUTURE_SELF=ag:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # (existing)
MISTRAL_AGENT_ID_INTERVIEW=ag:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MISTRAL_AGENT_ID_PROFILE_EXTRACTION=ag:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MISTRAL_AGENT_ID_CURRENT_SELF_GENERATION=ag:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Voice pool (example with ElevenLabs voice IDs):
ELEVENLABS_VOICE_POOL_JSON={"elevated":"21m00Tcm4TlvDq8ikWAM","warm":"AZnzlk1XvdvUeBnXmlld","sharp":"EXAVITQu4vr4xnSDxMaL","grounded":"ErXwobaYiN019PkySvjV","calm":"MF3mGyEYCl7XYWbV9V6O","intense":"VR6AewLTigWG4xSOukaG","ethereal":"pNInz6obpgDQGcFmaJgB"}
```

### 3. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Start API Server

```bash
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 5. Test Endpoints

```bash
# Start interview
curl -X POST http://localhost:8000/interview/start \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test_001", "user_name": "Alice"}'

# Send user message
curl -X POST http://localhost:8000/interview/reply \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test_001", "user_message": "Im in tech, feeling torn about a big move"}'

# Check status
curl http://localhost:8000/interview/status?session_id=test_001

# Complete interview
curl -X POST http://localhost:8000/interview/complete \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test_001"}'
```

---

## Integration with Future-Self System

Once onboarding completes:

1. `currentSelf` is saved to session
2. User is ready for `/future-self/generate`
3. System creates 2-3 contrasting future personas
4. User explores consequences via conversation
5. Multi-level branching ensues (existing system)

### Example Flow

```
User profile: High-performer torn between career acceleration and family stability
Current Dilemma: "Accept Singapore VP or stay in NYC?"

↓

CurrentSelf Generated:
- Optimization Goal: "Balance career growth, marital stability, financial security"
- Tone: "Measured, reflective, slightly tense"
- Worldview: "Best decisions create momentum without damaging what matters most"

↓

Future Self Options Generated:
1. "Self Who Took the Singapore Move"
   - Optimization: "Maximize career acceleration"
   - Tone: "Calm, confident, emotionally controlled"
   
2. "Self Who Stayed in New York"
   - Optimization: "Preserve relational stability"
   - Tone: "Warm, steady, emotionally available"

↓

User selects one → Conversation begins → Learns about trade-offs
```

---

## Testing

### Unit Tests

```bash
cd backend
python3 -m pytest test_onboarding_flow.py -v
```

### Manual Integration Test

```bash
python3 backend/test_onboarding_flow.py
```

This validates:
- All profile schemas work
- Extended UserProfile round-trips JSON
- Extraction output validates with confidence scores
- CurrentSelf SelfCard generation works
- Complete flow from interview → profile → CurrentSelf → ready

---

## Error Handling

### Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| `MISTRAL_AGENT_ID_PROFILE_EXTRACTION not set` | Missing .env value | Add agent ID from console.mistral.ai |
| `Mistral output failed schema validation` | Mistral returned invalid JSON | Verify agent system prompt was pasted completely |
| `Profile completeness stuck at 50%` | Interview agent not covering all dimensions | Agent needs system prompt with dimension guidance |
| `CurrentSelf generation fails` | Profile data missing required fields | Check profile has `current_dilemma`, `core_values`, `fears` |

---

## Architecture Details

### Session Memory Model

- **In-Memory**: Interview session lives in `_INTERVIEW_SESSIONS[session_id]` during interview phase
- **Disk**: `session.json` updated after each profile extraction
- **Cleanup**: Session removed from memory when `/interview/complete` called

### Prompt Composition

Interview agent uses `PromptComposer` to build messages:

```
System Prompt (interview_agent.md) +
Conversation History (last 10 turns) +
User Message
↓
Sent to Mistral API
↓
Response streamed back
```

### Profile Merging Strategy

When extraction returns new data:

```python
def merge(existing, extracted, confidence):
    if confidence >= 0.7 and extracted:
        return extracted  # High confidence: use new data
    else:
        return existing or extracted  # Low confidence: keep existing
```

This preserves earlier high-confidence extractions while allowing refinement.

---

## Future Enhancements

1. **Streaming Interview Responses**: Use `stream_reply()` for real-time UI updates
2. **Voice Interview**: Integrate ElevenLabs STT/TTS for phone-like experience
3. **Adaptive Prompting**: Adjust interview questions based on profile completeness
4. **Profile Refinement**: Allow users to edit profile before CurrentSelf generation
5. **Multi-language**: Support interview in different languages
6. **Branching from Profiles**: Generate futures at different timeframes (5yr, 10yr, 20yr)

---

## Files Modified/Created

### New Files
- `backend/app.py` - FastAPI application server
- `backend/routers/onboarding.py` - Interview/onboarding endpoints
- `backend/engines/profile_extractor.py` - Profile extraction engine
- `backend/engines/current_self_auto_generator.py` - CurrentSelf generation engine
- `backend/test_onboarding_flow.py` - Integration tests
- `prompts/interview_agent.md` - Interview system prompt
- `prompts/profile_extraction.md` - Profile extraction system prompt

### Modified Files
- `backend/models/schemas.py` - Added profile structures and extraction schemas
- `backend/config/settings.py` - Added new agent IDs and paths
- `backend/routers/interview.py` - Placeholder with note to use onboarding

---

## Summary

This onboarding system creates a **fluid, conversational experience** that:

✓ Feels natural (no mechanical checklists)
✓ Progressively builds user profile across 6 life dimensions
✓ Tracks extraction confidence to guide completeness
✓ Auto-generates a CurrentSelf persona reflecting present tensions
✓ Triggers the future-self exploration system once dilemma is explicit

The hybrid flow balances **real-time feedback** (incremental updates) with **natural conversation** (progressive emergence of dilemma), resulting in deeply personalized self-exploration.
