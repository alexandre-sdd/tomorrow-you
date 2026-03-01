# Engines — Core AI Logic Classes

## Purpose

Each engine is a Python class that encapsulates one stage of the pipeline. They are stateless services — session state is passed in and returned, not stored internally. This keeps them testable and composable.

## Engines

### 1. InterviewAgent

**File**: `interview_agent.py`
**Input**: conversation history (list of messages), user's latest message
**Output**: next interviewer question OR signal that the interview is complete
**Behavior**:

- Asks 5-8 thoughtful questions to extract values, fears, tensions, decision style, and the user's current dilemma
- Neutral, impersonal tone — not a therapist, not a friend, just a clean interviewer
- Decides when enough signal has been gathered and ends the interview
- Uses Mistral with a structured system prompt from `prompts/interview.md`

### 2. ProfileBuilder

**File**: `profile_builder.py`
**Input**: full interview transcript
**Output**: structured `UserProfile` object
**Behavior**:

- Takes the raw transcript and extracts: core values, fears, hidden tensions, decision style, self-narrative, current dilemma
- Also generates the **current self** — a persona card representing who the user is right now (name, optimization goal, tone, worldview, core belief, trade-off, visual style)
- This is the emotional anchor: users see themselves reflected before seeing future selves
- Uses Mistral with structured output / JSON mode

### 3. FutureSelfGenerator

**File**: `future_self_generator.py`
**Input**: `UserProfile` + current self card
**Output**: list of 2-3 `SelfCard` objects (the future self options)
**Behavior**:

- Takes the dilemma and profile, then generates contrasting future personas
- Each persona optimizes for something different (e.g., ambition vs. peace vs. love)
- Each has: name, optimization goal, tone of voice, worldview, core belief, trade-off/sacrifice, visual style
- The variation comes from changing which values are prioritized and which are sacrificed
- Uses Mistral with a generation prompt from `prompts/future_self_generation.md`

#### Future Enhancements

1. **Depth Limits**: Enforce max depth per session
2. **Branch Pruning**: Allow removing unwanted branches
3. **Path Comparison**: Compare different paths side-by-side
4. **Conversation Context**: Use parent conversations in secondary generation
5. **Visual Tree UI**: Frontend tree visualization with navigation

### 4. ConversationEngine

**File**: `conversation_engine.py`
**Input**: selected `SelfCard`, user message, conversation history, memory facts
**Output**: response text + updated memory facts
**Behavior**:

- Responds as the future self with the persona's tone, worldview, and beliefs
- Maintains short-term conversation memory (recent messages)
- Extracts key facts from each exchange and stores them as memory
- Stays in character — never breaks persona, never admits to being AI
- Uses Mistral with a dynamic system prompt built from the SelfCard

### 5. VoicePipeline

**File**: `voice_pipeline.py`
**Input**: raw audio bytes (from user mic)
**Output**: transcribed text + synthesized audio response
**Behavior**:

- Transcription: user audio → text via **ElevenLabs STT** (speech-to-text)
- Synthesis: response text → voice audio via **ElevenLabs TTS** (text-to-speech, streaming)
- The entire voice pipeline is ElevenLabs end-to-end — no Whisper, no Deepgram
- Supports streaming: start playing audio before the full response is generated
- Each future self has a distinct ElevenLabs voice ID
- Interview agent uses a neutral default voice; future selves each get a unique voice

### 6. AvatarGenerator

**File**: `avatar_generator.py`
**Input**: `SelfCard` (persona details + visual style description)
**Output**: generated image URL or base64 image data
**Behavior**:

- Generates a stylized avatar image for each self using **Mistral (Pixtral) or Google Gemini** image generation
- Takes the persona's name, mood, visual style description, and optimization goal to craft an image prompt
- Generates a new image when a self is first created (current self, each future self)
- The avatar should feel like a stylized, slightly abstract portrait — not photorealistic, not cartoon
- Generated images are cached in storage so we don't regenerate on every page load
- Falls back between providers: try Mistral Pixtral first, fall back to Gemini if unavailable

## How They Connect

```
User Audio → VoicePipeline.transcribe() [ElevenLabs STT]
          → ConversationEngine.respond() [Mistral LLM]
          → VoicePipeline.synthesize() [ElevenLabs TTS]
          → Audio + Subtitles back to frontend

Profile Built → AvatarGenerator.generate(currentSelf) [Mistral Pixtral / Gemini]
             → Image displayed in Profile Reveal

Future Selves Generated → AvatarGenerator.generate(futureSelf) [for each]
                       → Images displayed on PersonaCards + Conversation Chamber
```

## CLI MVP Modules (Implemented)
### `context_resolver.py`
- Read-only loader for `storage/sessions/{session_id}/...`
- Resolves one branch (`memory/branches.json` + `memory/nodes/*.json`) into:
  - `userProfile`
  - selected branch `selfCard`
  - merged memory facts/notes from root → head
- compact profile summary for prompting
- Does not write any session or memory files

### `conversation_memory.py`
- Persists conversation turns to `transcript.json` (`user`/`assistant`)
- Runs LLM transcript analysis (few-shot prompt) to extract open-ended key elements at checkpoint events (exit/rebranch)
- Appends extracted insights to current branch node `facts` and `notes`, and adds `memory` entries to transcript
- Keeps `session.json.memoryNodes` mirror synchronized when present

### `prompt_composer.py`
- Builds a branch-grounded system prompt from resolved context
- Produces model-ready message arrays (`system` + rolling history + latest user turn)
- Keeps prompt compact with configurable caps for facts/notes/history

### `mistral_client.py`
- Thin Mistral chat wrapper using `MISTRAL_API_KEY`
- Supports synchronous (`chat`) and streaming (`stream_chat`) completion calls
- Returns plain text chunks for CLI rendering

### `conversation_session.py`
- In-memory branch conversation orchestrator
- Uses: `ResolvedConversationContext` + `PromptComposer` + `MistralChatClient`
- Tracks only rolling turn history in memory; no storage writes

### `backend/cli/chat_future_self.py`
- Terminal REPL for chatting with a selected future-self branch
- Inputs: `--session-id` plus either `--self-id` or `--branch`, plus model/config flags
- Persists each successful turn to transcript
- On exit, analyzes the transcript and commits extracted insights to branch memory
- Commands:
  - `/context`, `/reset`, `/help`, `/exit`
  - `/branch [2|3] [optional time horizon]` to generate children and pick a new path
  - `/branch-reprompt [2|3] [optional time horizon]` to branch and re-ask the last prompt on the selected path
  - `/reprompt` to ask the same last user message again on the current path

### `backend/cli/generate_future_selves.py`
- Terminal helper to run the same generation flow as `POST /future-self/generate`
- Supports root-level (`--parent-self-id` omitted) and deeper branching (`--parent-self-id <id>`)
- Prints generated self IDs so chat can start immediately with `--self-id`

### `CONVERSATION_ENGINE_MVP.md`
- Defines scope and boundaries for the first CLI-only version
- Excludes voice and UI for this phase

## TODO

- [ ] Create base engine class/interface
- [ ] Implement InterviewAgent with Mistral
- [ ] Implement ProfileBuilder with structured output
- [ ] Implement FutureSelfGenerator with persona card schema
- [ ] Implement ConversationEngine with memory extraction
- [ ] Implement VoicePipeline with ElevenLabs STT + TTS (fully ElevenLabs)
- [ ] Implement AvatarGenerator with Mistral Pixtral / Gemini fallback
- [ ] Write unit tests for each engine with mock LLM responses
