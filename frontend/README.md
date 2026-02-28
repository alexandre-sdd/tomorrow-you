# Frontend — Next.js / React / Tailwind

## Purpose
The entire user-facing application. A Next.js app with Tailwind CSS that delivers a premium, voice-first experience across 6 main screens.

## Tech Stack
- **Framework**: Next.js 14+ (App Router)
- **Styling**: Tailwind CSS + custom design tokens for self themes
- **State**: Zustand (lightweight, fits the linear-with-branching flow)
- **Voice**: ElevenLabs end-to-end (STT + TTS via WebSocket streaming)
- **Animations**: Framer Motion for avatar transitions and screen reveals

## Screens (in user flow order)
1. **Landing** — premium intro, CTA to begin
2. **Interview** — neutral AI interviewer (voice/text), waveform visualizer
3. **Profile Reveal** — animated reveal of the user's structured identity + current self avatar
4. **Future Self Selection** — 2-3 persona cards with distinct visual identities
5. **Conversation Chamber** — live voice conversation with the selected future self
6. **Debrief** — summary of what this self optimizes, sacrifices, and gains

## Interaction with Backend
- All API calls go through `lib/api.ts` which wraps fetch/WebSocket calls
- Interview & conversation screens use **WebSocket** connections for real-time streaming
- Profile build and future self generation use standard **REST** calls (POST)
- Voice audio is streamed as raw PCM/opus chunks over WebSocket

## Key Design Decisions
- Voice-first: microphone is the primary input, text is secondary/fallback
- Avatar is an AI-generated image (Mistral Pixtral / Gemini) — UI renders it with glow, effects, and crossfade transitions between selves
- Subtitles render in real-time as the AI speaks, synced to the audio stream
- All transitions between screens should feel cinematic, not like page navigation

## State Management
```
SessionStore {
  currentScreen: Screen
  transcript: TranscriptEntry[]         // linear log, append-only
  userProfile: UserProfile | null
  currentSelf: SelfCard | null
  futureSelvesOptions: SelfCard[]
  selectedFutureSelf: SelfCard | null
  memoryHead: string                    // current branch name
  resolvedMemory: KeyFact[]             // flattened facts from root→HEAD (from backend)
}
```

## TODO
- [ ] Initialize Next.js project with Tailwind
- [ ] Set up app router with the 6 screen routes
- [ ] Create Zustand session store with TypeScript types
- [ ] Build Landing page with CTA
- [ ] Build Interview screen with mic input + waveform
- [ ] Build Profile Reveal screen with avatar component
- [ ] Build Future Self Selection screen with persona cards
- [ ] Build Conversation Chamber with real-time subtitles
- [ ] Build Debrief summary screen
- [ ] Create reusable Avatar component that accepts a SelfCard theme
- [ ] Set up WebSocket client for voice streaming
- [ ] Create API client wrapper (lib/api.ts)
- [ ] Add screen transition animations
