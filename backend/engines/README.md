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
- Uses Mistral with a generation prompt from `prompts/future_self.md`

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

## TODO
- [ ] Create base engine class/interface
- [ ] Implement InterviewAgent with Mistral
- [ ] Implement ProfileBuilder with structured output
- [ ] Implement FutureSelfGenerator with persona card schema
- [ ] Implement ConversationEngine with memory extraction
- [ ] Implement VoicePipeline with ElevenLabs STT + TTS (fully ElevenLabs)
- [ ] Implement AvatarGenerator with Mistral Pixtral / Gemini fallback
- [ ] Write unit tests for each engine with mock LLM responses
