# Components — Reusable React/UI Components

## Purpose
Shared UI components used across multiple screens. These are the building blocks of the visual experience. Given that UI polish is the #1 hackathon priority, these components need to feel premium and cohesive.

## Key Components

### `Avatar.tsx`
The central visual element of the product. Displays an **AI-generated image** of the self (current or future), created by Mistral Pixtral or Google Gemini on the backend.
- **Input**: a `SelfCard` (specifically `avatarUrl` for the image, `visualStyle` for surrounding UI effects)
- **Image source**: the avatar image is generated server-side via `/avatar/generate` and the URL is stored on the SelfCard — this component displays that image
- **UI effects**: the surrounding glow, particle effects, and color palette come from `visualStyle` and are rendered with CSS/Framer Motion around the generated image
- **Transitions**: crossfade/morph between avatar images when switching selves
- **States**: idle (static image + subtle glow), listening (glow pulses with mic input), speaking (glow intensifies with audio), transitioning (crossfade between images)
- **Loading**: shows a shimmer/skeleton while the avatar image is being generated
- This is the most important component — it makes or breaks the demo

### `Waveform.tsx`
Audio visualization for mic input and AI speech output.
- Shows when the user is speaking (input waveform)
- Shows when the AI is speaking (output waveform)
- Styled to match the current self's visual theme

### `SubtitleOverlay.tsx`
Real-time subtitles during voice conversation.
- Renders text as it streams from the AI response
- Fades out after a delay
- Positioned over/near the avatar

### `PersonaCard.tsx`
Card component for the future self selection screen.
- Displays: name, optimization goal, trade-off, AI-generated avatar image
- Click/tap to select
- Shows the generated avatar image as the card's visual centerpiece
- Card border/glow uses the self's `visualStyle` colors

### `MicButton.tsx`
Push-to-talk or toggle mic button with visual feedback.
- States: inactive, recording, processing
- Pulsing animation while recording
- Integrates with Web Audio API for mic access

### `ScreenTransition.tsx`
Wrapper component for cinematic transitions between screens.
- Fade, slide, or morph transitions using Framer Motion
- Each screen transition should feel intentional, not like a page load

## Design Tokens
All components pull from a shared design token system:
- Colors, shadows, blur, glow effects
- These tokens change based on the active `SelfCard.visualStyle`
- This creates the effect of the entire UI "becoming" the selected self

## TODO
- [ ] Build Avatar component displaying AI-generated image with glow/effects overlay
- [ ] Build avatar loading/shimmer state for while image generates
- [ ] Build Waveform audio visualizer
- [ ] Build SubtitleOverlay with streaming text
- [ ] Build PersonaCard with generated avatar image
- [ ] Build MicButton with recording states
- [ ] Build ScreenTransition wrapper
- [ ] Create design token system that adapts to SelfCard themes
- [ ] Add Framer Motion animations for avatar state changes and crossfades
