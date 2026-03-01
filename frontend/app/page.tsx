"use client";

import { useState } from "react";
import AppShell from "../components/AppShell";
import { mockSingaporeSelf, mockUserProfile } from "../lib/mocks";
import { SelfCard, UserProfile } from "../lib/types";
import FutureSelfConversationScreen from "../screens/FutureSelfConversationScreen";
import InterviewScreen from "../screens/InterviewScreen";
import LandingScreen from "../screens/LandingScreen";
import ProfileRevealScreen from "../screens/ProfileRevealScreen";

type PrototypeScreen = "landing" | "interview" | "profile" | "conversation";

export default function HomePage() {
  const [screen, setScreen] = useState<PrototypeScreen>("landing");
  const [activeProfile, setActiveProfile] = useState<UserProfile>(mockUserProfile);
  const [activeCurrentSelf, setActiveCurrentSelf] = useState<SelfCard | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  return (
    <AppShell>
      {screen === "landing" && <LandingScreen onBegin={() => setScreen("interview")} />}

      {screen === "interview" && (
        <InterviewScreen
          onComplete={({ sessionId, profile, currentSelf }) => {
            setActiveSessionId(sessionId);
            if (profile) {
              setActiveProfile(profile);
            }
            setActiveCurrentSelf(currentSelf);
            setScreen("profile");
          }}
        />
      )}

      {screen === "profile" && (
        <>
          <ProfileRevealScreen profile={activeProfile} onContinue={() => setScreen("conversation")} />
          <p className="prototype-footnote">
            Session: {activeSessionId ?? "not-set"}{" "}
            {activeCurrentSelf ? `• Current Self: ${activeCurrentSelf.name}` : ""}
          </p>
        </>
      )}

      {screen === "conversation" && <FutureSelfConversationScreen selfCard={mockSingaporeSelf} />}
    </AppShell>
  );
}
