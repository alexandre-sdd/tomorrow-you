# Lib — Frontend Utilities & Services

## Purpose
Shared utilities, API client, and service wrappers used across screens and components. Keeps screens thin by extracting API calls, audio handling, and state management.

## Files

### `api.ts`
Centralized API client wrapping all backend calls.
- `interviewRespond(sessionId, message)` → next interviewer question
- `buildProfile(sessionId)` → UserProfile + CurrentSelf
- `generateFutureSelves(sessionId)` → SelfCard[]
- `selectFutureSelf(sessionId, selfId)` → confirmation
- `summarizeConversation(sessionId)` → debrief data
- `generateAvatar(sessionId, selfId)` → generated avatar image URL
- `backtrack(sessionId, targetBranch)` → switch branch, get updated session
- Handles auth headers, error formatting, base URL config

### `websocket.ts`
WebSocket client for real-time voice conversation.
- Connects to `/conversation/stream`
- Sends audio chunks from mic
- Receives text (subtitles) and audio (AI voice) streams
- Handles reconnection and error states

### `audio.ts`
Web Audio API utilities.
- `startRecording()` → MediaStream + audio chunk emitter
- `stopRecording()` → final audio buffer
- `playAudioStream(chunks)` → plays ElevenLabs audio chunks in real-time
- `getAudioLevel()` → current mic amplitude (for waveform visualization)

### `store.ts`
Zustand store definition (SessionStore) and actions.
- Holds the full session state
- Actions for each step: `setTranscript`, `setProfile`, `selectSelf`, `addMessage`, etc.
- Persist middleware for surviving page refreshes

### `types.ts`
TypeScript type definitions matching the shared schemas.
- `UserProfile`, `SelfCard`, `TranscriptEntry`, `KeyFact`, `MemoryNode`, `MemoryBranch`, `Session`
- Single source of TS types, imported everywhere

### `mocks.ts`
Seed mock data for UI and flow development.
- `mockUserProfile`
- `mockSelfCards`
- `mockStayInNYCSelf`
- `mockFutureSelfOptions`
- `mockSession`
- Mirrors the storage seed in `storage/sessions/user_nyc_singapore_001/`

## TODO
- [ ] Create API client with all endpoint wrappers
- [ ] Create WebSocket client for conversation streaming
- [ ] Create audio utilities (recording, playback, level detection)
- [ ] Create Zustand store with session state and actions
- [x] Create TypeScript types matching shared schemas
