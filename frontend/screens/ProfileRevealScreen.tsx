"use client";

import ProfileCard from "../components/ProfileCard";
import ScreenHeader from "../components/ScreenHeader";
import { UserProfile } from "../lib/types";

interface ProfileRevealScreenProps {
  profile: UserProfile;
  onContinue: () => void;
}

export default function ProfileRevealScreen({ profile, onContinue }: ProfileRevealScreenProps) {
  return (
    <div className="screen screen--profile">
      <ScreenHeader
        eyebrow="Profile Reveal"
        title="Your Present Self, Mapped"
        subtitle="A first-pass profile extracted from your interview context."
      />
      <ProfileCard profile={profile} />
      <div className="screen-actions">
        <button className="button-pill" type="button" onClick={onContinue}>
          Continue to Future Self
        </button>
      </div>
    </div>
  );
}
