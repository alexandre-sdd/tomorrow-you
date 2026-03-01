"use client";

import { ProfileCard } from "@/components/ProfileCard";
import { ScreenHeader } from "@/components/ScreenHeader";
import type { SelfCard, UserProfile } from "@/lib/types";

interface ProfileRevealScreenProps {
  profile: UserProfile;
  currentSelf: SelfCard;
  onContinue: () => void;
}

export function ProfileRevealScreen({ profile, currentSelf, onContinue }: ProfileRevealScreenProps) {
  return (
    <section className="stack-screen">
      <ScreenHeader
        eyebrow="Onboarding complete"
        title="Your current self is ready"
        subtitle="This profile snapshot will anchor future branching and conversations."
      />

      <ProfileCard profile={profile} />

      <article className="surface-card current-self-card">
        <h3>{currentSelf.name}</h3>
        <p>{currentSelf.optimizationGoal}</p>
      </article>

      <button type="button" onClick={onContinue} className="primary-cta">
        View future selves
      </button>
    </section>
  );
}
