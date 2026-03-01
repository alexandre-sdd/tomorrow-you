"use client";

import { ScreenHeader } from "@/components/ScreenHeader";
import { SelfCardPanel } from "@/components/SelfCardPanel";
import type { SelfCard } from "@/lib/types";

interface SelfSelectionScreenProps {
  futureSelves: SelfCard[];
  activeSelfId: string | null;
  isRefreshingStatus: boolean;
  onRefreshStatus: () => Promise<void>;
  onSelectSelf: (selfId: string) => void;
  onStartConversation: () => void;
}

export function SelfSelectionScreen({
  futureSelves,
  activeSelfId,
  isRefreshingStatus,
  onRefreshStatus,
  onSelectSelf,
  onStartConversation,
}: SelfSelectionScreenProps) {
  return (
    <section className="stack-screen">
      <ScreenHeader
        eyebrow="Exploration"
        title="Choose who you want to meet"
        subtitle="Pick a future self path. You can always return and branch again later."
      />

      <div className="status-actions">
        <button
          type="button"
          className="ghost-button"
          onClick={onRefreshStatus}
          disabled={isRefreshingStatus}
        >
          {isRefreshingStatus ? "Refreshing..." : "Refresh pipeline status"}
        </button>
      </div>

      <div className="self-grid">
        {futureSelves.map((selfCard) => (
          <SelfCardPanel
            key={selfCard.id}
            selfCard={selfCard}
            isActive={activeSelfId === selfCard.id}
            onClick={() => onSelectSelf(selfCard.id)}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={onStartConversation}
        disabled={!activeSelfId}
        className="primary-cta"
      >
        Start conversation
      </button>
    </section>
  );
}
