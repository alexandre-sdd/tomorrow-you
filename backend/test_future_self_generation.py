"""
Test script to validate the agentic future self generation system.

This script:
1. Loads the mock user profile and current self from session.json
2. Generates new future selves using the FutureSelfGenerator
3. Compares the generated personas with the existing mock personas
4. Provides detailed analysis of quality and similarity

Usage:
    python backend/test_future_self_generation.py
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from backend.config.settings import get_settings
from backend.engines.future_self_generator import FutureSelfGenerator, GenerationContext
from backend.models.schemas import SelfCard, UserProfile

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SESSION_PATH = Path("storage/sessions/user_nyc_singapore_001/session.json")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def load_mock_data() -> tuple[UserProfile, SelfCard, list[SelfCard]]:
    """Load user profile, current self, and existing future selves from session.json"""
    if not SESSION_PATH.exists():
        raise FileNotFoundError(f"Session file not found: {SESSION_PATH}")
    
    with SESSION_PATH.open("r", encoding="utf-8") as f:
        session_data = json.load(f)
    
    # Parse user profile
    user_profile = UserProfile.model_validate(session_data["userProfile"])
    
    # Parse current self
    current_self = SelfCard.model_validate(session_data["currentSelf"])
    
    # Parse existing future selves
    existing_future_selves = [
        SelfCard.model_validate(self_data)
        for self_data in session_data.get("futureSelfOptions", [])
    ]
    
    return user_profile, current_self, existing_future_selves


def print_self_card(card: SelfCard, label: str = "Self Card") -> None:
    """Pretty print a SelfCard for comparison"""
    print(f"\n{'=' * 80}")
    print(f"{label}: {card.name}")
    print(f"{'=' * 80}")
    print(f"ID: {card.id}")
    print(f"Type: {card.type}")
    print(f"\nOptimization Goal:")
    print(f"  {card.optimization_goal}")
    print(f"\nTone of Voice:")
    print(f"  {card.tone_of_voice}")
    print(f"\nWorldview:")
    print(f"  {card.worldview}")
    print(f"\nCore Belief:")
    print(f"  {card.core_belief}")
    print(f"\nTrade-off:")
    print(f"  {card.trade_off}")
    print(f"\nAvatar Prompt:")
    print(f"  {card.avatar_prompt}")
    print(f"\nVisual Style:")
    print(f"  Primary Color: {card.visual_style.primary_color}")
    print(f"  Accent Color: {card.visual_style.accent_color}")
    print(f"  Mood: {card.visual_style.mood}")
    print(f"  Glow Intensity: {card.visual_style.glow_intensity}")
    print(f"\nVoice ID: {card.voice_id}")


def analyze_personas(
    generated: list[SelfCard],
    existing: list[SelfCard],
    user_profile: UserProfile,
    current_self: SelfCard,
) -> None:
    """Analyze and compare generated personas with existing ones"""
    print("\n" + "=" * 80)
    print("ANALYSIS: Generated vs. Existing Personas")
    print("=" * 80)
    
    # 1. Count check
    print(f"\n1. COUNT:")
    print(f"   Generated: {len(generated)} personas")
    print(f"   Expected: {len(existing)} personas")
    if len(generated) == len(existing):
        print("   ✓ Count matches")
    else:
        print("   ⚠ Count mismatch")
    
    # 2. Contrast check
    print(f"\n2. CONTRAST (Different optimization goals):")
    goals = [s.optimization_goal for s in generated]
    print(f"   Generated goals:")
    for i, goal in enumerate(goals, 1):
        print(f"     {i}. {goal}")
    
    # Check if goals are meaningfully different
    if len(set(goals)) == len(goals):
        print("   ✓ All optimization goals are unique")
    else:
        print("   ⚠ Some optimization goals may be too similar")
    
    # 3. Visual style diversity
    print(f"\n3. VISUAL DIVERSITY:")
    moods = [s.visual_style.mood for s in generated]
    colors = [s.visual_style.primary_color for s in generated]
    print(f"   Moods: {', '.join(moods)}")
    print(f"   Primary Colors: {', '.join(colors)}")
    if len(set(moods)) == len(moods) and len(set(colors)) == len(colors):
        print("   ✓ All moods and colors are unique")
    else:
        print("   ⚠ Some moods or colors are duplicated")
    
    # 4. Voice assignment
    print(f"\n4. VOICE ASSIGNMENT:")
    voice_ids = [s.voice_id for s in generated]
    for i, (self, voice) in enumerate(zip(generated, voice_ids), 1):
        print(f"   {i}. {self.name}")
        print(f"      Mood: {self.visual_style.mood} → Voice: {voice}")
    if len(set(voice_ids)) == len(voice_ids):
        print("   ✓ All voice IDs are unique")
    else:
        print("   ⚠ Some voice IDs are duplicated")
    
    # 5. Trade-off authenticity
    print(f"\n5. TRADE-OFF AUTHENTICITY:")
    for i, self in enumerate(generated, 1):
        print(f"   {i}. {self.name}:")
        print(f"      {self.trade_off}")
        # Check for first-person language
        first_person = any(word in self.trade_off.lower() for word in ["i ", "my ", "i'm", "i've"])
        if first_person:
            print(f"      ✓ Uses first-person voice")
        else:
            print(f"      ⚠ May not use first-person voice")
    
    # 6. Avatar prompt quality
    print(f"\n6. AVATAR PROMPT QUALITY:")
    for i, self in enumerate(generated, 1):
        sentence_count = len([s for s in self.avatar_prompt.split('.') if s.strip()])
        print(f"   {i}. {self.name}: {sentence_count} sentences")
        if 3 <= sentence_count <= 5:
            print(f"      ✓ Appropriate length")
        else:
            print(f"      ⚠ May be too short or too long ({sentence_count} sentences)")
    
    # 7. Alignment with user profile
    print(f"\n7. ALIGNMENT WITH USER PROFILE:")
    print(f"   User's core values: {', '.join(user_profile.core_values)}")
    print(f"   User's fears: {', '.join(user_profile.fears)}")
    print(f"   Current dilemma: {user_profile.current_dilemma}")
    print(f"\n   Generated personas should address these values and fears")
    print(f"   with different life paths.")
    
    # 8. Similarity to existing mocks
    print(f"\n8. SIMILARITY TO EXISTING MOCK PERSONAS:")
    print(f"   Existing persona names:")
    for i, self in enumerate(existing, 1):
        print(f"     {i}. {self.name}")
    print(f"\n   Generated persona names:")
    for i, self in enumerate(generated, 1):
        print(f"     {i}. {self.name}")
    print(f"\n   The generated personas should be different specific futures")
    print(f"   but similar in quality and depth to the existing ones.")


# ---------------------------------------------------------------------------
# Main test function
# ---------------------------------------------------------------------------

async def main() -> None:
    """Main test function"""
    print("=" * 80)
    print("FUTURE SELF GENERATION TEST")
    print("=" * 80)
    
    # Check environment
    try:
        settings = get_settings()
        print(f"\n✓ Settings loaded successfully")
        print(f"  Mistral API Key: {'*' * 8}{settings.mistral_api_key[-4:] if settings.mistral_api_key else 'NOT SET'}")
        print(f"  Mistral Agent ID: {settings.mistral_agent_id_future_self[:20]}...")
        print(f"  ElevenLabs API Key: {'*' * 8}{settings.elevenlabs_api_key[-4:] if settings.elevenlabs_api_key else 'NOT SET'}")
        print(f"  Voice Pool: {len(settings.elevenlabs_voice_pool)} moods configured")
    except Exception as e:
        print(f"\n✗ Error loading settings: {e}")
        print("\nPlease ensure you have a .env file with required configuration.")
        print("See .env.example for reference.")
        return
    
    # Load mock data
    print("\n" + "-" * 80)
    print("Loading mock data from session.json...")
    print("-" * 80)
    try:
        user_profile, current_self, existing_future_selves = load_mock_data()
        print(f"\n✓ Mock data loaded successfully")
        print(f"  User Profile ID: {user_profile.id}")
        print(f"  Current Self: {current_self.name}")
        print(f"  Existing Future Selves: {len(existing_future_selves)}")
    except Exception as e:
        print(f"\n✗ Error loading mock data: {e}")
        return
    
    # Print existing personas for reference
    print("\n" + "-" * 80)
    print("EXISTING MOCK PERSONAS (for comparison)")
    print("-" * 80)
    for i, self in enumerate(existing_future_selves, 1):
        print_self_card(self, f"Existing Persona {i}")
    
    # Generate new personas
    print("\n" + "-" * 80)
    print("Generating new future selves using the agent...")
    print("-" * 80)
    try:
        generator = FutureSelfGenerator()
        ctx = GenerationContext(
            user_profile=user_profile,
            current_self=current_self,
            count=2,
        )
        generated_selves = await generator.generate(ctx)
        print(f"\n✓ Generation successful! Created {len(generated_selves)} personas")
    except Exception as e:
        print(f"\n✗ Error generating personas: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Print generated personas
    print("\n" + "-" * 80)
    print("NEWLY GENERATED PERSONAS")
    print("-" * 80)
    for i, self in enumerate(generated_selves, 1):
        print_self_card(self, f"Generated Persona {i}")
    
    # Analyze and compare
    analyze_personas(
        generated=generated_selves,
        existing=existing_future_selves,
        user_profile=user_profile,
        current_self=current_self,
    )
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\nThe generated personas should:")
    print("  1. Match the quality and depth of the existing mock personas")
    print("  2. Represent genuinely different life paths based on the dilemma")
    print("  3. Have authentic trade-offs that feel real and costly")
    print("  4. Use distinct visual styles and voice assignments")
    print("  5. Address the user's core values and fears in different ways")


if __name__ == "__main__":
    asyncio.run(main())
