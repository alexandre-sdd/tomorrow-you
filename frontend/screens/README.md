# Screens — Page-Level Components (App Router)

## Purpose
Each screen corresponds to a step in the user flow and a Next.js route. Screens compose components, manage screen-level state, and handle API interactions for their step.

## Screens

### `Landing.tsx` → `/`
- Premium intro with product tagline
- Animated background or subtle particle effect
- Single CTA button: "Begin" or "Meet Your Future Self"
- Creates a new session on click, then navigates to Interview

### `Interview.tsx` → `/interview`
- The neutral AI interviewer asks questions via voice and/or text
- User responds via mic (primary) or text input (fallback)
- Shows a neutral/generic avatar (not yet personalized)
- Waveform visualizer active during speech
- When the interviewer signals completion, auto-navigates to Profile Reveal
- **API**: WebSocket or polling to `/interview/respond`

### `ProfileReveal.tsx` → `/profile`
- Animated reveal of the user's structured profile
- Shows values, fears, tensions, decision style
- Introduces the **current self** — first time the avatar becomes personalized
- Avatar morphs from neutral to the current self's visual identity
- "This is you right now" moment — emotional anchor
- CTA: "See your possible futures"
- **API**: `POST /profile/build`

### `FutureSelfSelect.tsx` → `/select`
- 2-3 PersonaCards displayed with distinct visual identities
- Each card shows: name, what it optimizes for, what it sacrifices
- Mini avatar preview on each card
- User taps to select → avatar morphs to the selected future self
- Confirmation moment before entering conversation
- **API**: `POST /future-self/generate`, then `POST /future-self/select`

### `ConversationChamber.tsx` → `/conversation`
- Full-screen voice conversation with the selected future self
- Large avatar center screen, styled for the selected self
- Waveform + subtitles active
- MicButton for user input
- Conversation flows naturally, AI stays in character
- "End conversation" button to proceed to debrief
- **API**: `WS /conversation/stream`

### `Debrief.tsx` → `/debrief`
- Summary of the conversation and the future self
- What this self optimizes for, what it sacrifices, what it gains
- Key moments or quotes from the conversation
- Option to go back and try a different future self (stretch goal)
- **API**: `POST /conversation/summarize`

## Screen Flow
```
Landing → Interview → ProfileReveal → FutureSelfSelect → ConversationChamber → Debrief
                                              ↑                                    |
                                              └────────── (try another self) ──────┘
```

## TODO
- [ ] Create Landing page with CTA and session creation
- [ ] Create Interview screen with voice input and neutral avatar
- [ ] Create ProfileReveal with animated profile display and current self
- [ ] Create FutureSelfSelect with persona cards
- [ ] Create ConversationChamber with full voice interaction
- [ ] Create Debrief summary screen
- [ ] Implement route guards (can't skip to conversation without a profile)
- [ ] Add loading/transition states between screens
