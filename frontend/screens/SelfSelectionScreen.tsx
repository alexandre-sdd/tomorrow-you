"use client";

import { useMemo, useState } from "react";
import { BranchTreeModal } from "@/components/BranchTreeModal";
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
  const [isTreeOpen, setIsTreeOpen] = useState(false);

  const byId = useMemo(() => {
    const map = new Map<string, SelfCard>();
    for (const selfCard of futureSelves) {
      map.set(selfCard.id, selfCard);
    }
    return map;
  }, [futureSelves]);

  const activeSelf = activeSelfId ? byId.get(activeSelfId) ?? null : null;

  const activePath = useMemo(() => {
    if (!activeSelf) {
      return [] as SelfCard[];
    }
    const path: SelfCard[] = [];
    const seen = new Set<string>();
    let cursor: SelfCard | null = activeSelf;

    while (cursor && !seen.has(cursor.id)) {
      path.push(cursor);
      seen.add(cursor.id);
      if (!cursor.parentSelfId) {
        break;
      }
      cursor = byId.get(cursor.parentSelfId) ?? null;
    }
    path.reverse();
    return path;
  }, [activeSelf, byId]);
  const maxDepth = useMemo(
    () => futureSelves.reduce((acc, selfCard) => Math.max(acc, selfCard.depthLevel), 0),
    [futureSelves],
  );

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

      <div className="selection-layout">
        <article className="surface-card branch-map-launcher-card">
          <p className="eyebrow">Branch Navigator</p>
          <h2>Open tree view</h2>
          <p className="branch-tree-hint">
            Use the popup map to navigate visually between futures. Each node uses its avatar.
          </p>
          <div className="branch-map-stats">
            <p>{futureSelves.length} futures generated</p>
            <p>Deepest branch: {maxDepth}</p>
          </div>
          <button type="button" onClick={() => setIsTreeOpen(true)}>
            Open branch map
          </button>
        </article>

        <article className="surface-card branch-detail-card">
          <p className="eyebrow">Selected Path</p>
          {activePath.length > 0 ? (
            <div className="path-chip-row">
              {activePath.map((node) => (
                <button
                  key={node.id}
                  type="button"
                  className={activeSelfId === node.id ? "path-chip path-chip-active" : "path-chip"}
                  onClick={() => onSelectSelf(node.id)}
                >
                  {node.name}
                </button>
              ))}
            </div>
          ) : (
            <p className="empty-text">Choose a future self from the tree.</p>
          )}

          {activeSelf ? (
            <SelfCardPanel
              selfCard={activeSelf}
              isActive
              onClick={() => onSelectSelf(activeSelf.id)}
            />
          ) : null}

          <button
            type="button"
            onClick={onStartConversation}
            disabled={!activeSelfId}
            className="primary-cta"
          >
            Start conversation
          </button>
        </article>
      </div>

      <BranchTreeModal
        isOpen={isTreeOpen}
        title="Choose Your Future Node"
        futureSelves={futureSelves}
        activeSelfId={activeSelfId}
        onSelectSelf={onSelectSelf}
        onClose={() => setIsTreeOpen(false)}
      />
    </section>
  );
}
