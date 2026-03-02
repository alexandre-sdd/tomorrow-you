"use client";

import { useMemo } from "react";
import { ScreenHeader } from "@/components/ScreenHeader";
import { SelfCardPanel } from "@/components/SelfCardPanel";
import type { SelfCard } from "@/lib/types";
import { getTimeHorizonLabel } from "@/lib/timeHorizon";

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
  const byId = useMemo(() => {
    const map = new Map<string, SelfCard>();
    for (const selfCard of futureSelves) {
      map.set(selfCard.id, selfCard);
    }
    return map;
  }, [futureSelves]);

  const childrenByParent = useMemo(() => {
    const map = new Map<string, SelfCard[]>();
    for (const selfCard of futureSelves) {
      const parent = selfCard.parentSelfId ?? "__root__";
      const list = map.get(parent) ?? [];
      list.push(selfCard);
      map.set(parent, list);
    }
    for (const list of map.values()) {
      list.sort((a, b) => {
        if (a.depthLevel !== b.depthLevel) {
          return a.depthLevel - b.depthLevel;
        }
        return a.name.localeCompare(b.name);
      });
    }
    return map;
  }, [futureSelves]);

  const rootNodes = useMemo(
    () =>
      futureSelves
        .filter((selfCard) => !selfCard.parentSelfId || !byId.has(selfCard.parentSelfId))
        .sort((a, b) => {
          if (a.depthLevel !== b.depthLevel) {
            return a.depthLevel - b.depthLevel;
          }
          return a.name.localeCompare(b.name);
        }),
    [futureSelves, byId],
  );

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

  const activePathIds = useMemo(() => new Set(activePath.map((selfCard) => selfCard.id)), [activePath]);

  const descendantCountById = useMemo(() => {
    const memo = new Map<string, number>();
    const countChildren = (nodeId: string): number => {
      const cached = memo.get(nodeId);
      if (cached !== undefined) {
        return cached;
      }
      const children = childrenByParent.get(nodeId) ?? [];
      const total = children.reduce((acc, child) => acc + 1 + countChildren(child.id), 0);
      memo.set(nodeId, total);
      return total;
    };
    for (const selfCard of futureSelves) {
      countChildren(selfCard.id);
    }
    return memo;
  }, [childrenByParent, futureSelves]);

  const renderTreeNode = (selfCard: SelfCard) => {
    const children = childrenByParent.get(selfCard.id) ?? [];
    const isActive = activeSelfId === selfCard.id;
    const isOnActivePath = activePathIds.has(selfCard.id);
    const descendantCount = descendantCountById.get(selfCard.id) ?? 0;
    const horizonLabel = getTimeHorizonLabel(selfCard.depthLevel);

    return (
      <article key={selfCard.id} className="tree-node-wrap">
        <button
          type="button"
          className={[
            "tree-node",
            isOnActivePath ? "tree-node-path" : "",
            isActive ? "tree-node-active" : "",
          ].join(" ").trim()}
          onClick={() => onSelectSelf(selfCard.id)}
        >
          <span className="tree-node-name">{selfCard.name}</span>
          <span className="tree-node-meta">Depth {selfCard.depthLevel} · {horizonLabel}</span>
          {descendantCount > 0 ? (
            <span className="tree-node-branch">
              {descendantCount} branch{descendantCount > 1 ? "es" : ""} below
            </span>
          ) : null}
        </button>

        {children.length > 0 ? (
          <div className="tree-children">
            {children.map((child) => renderTreeNode(child))}
          </div>
        ) : null}
      </article>
    );
  };

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
        <article className="surface-card branch-tree-card">
          <p className="eyebrow">Branch Navigator</p>
          <p className="branch-tree-hint">
            Your futures are organized as a branching tree. Pick any node to continue that path.
          </p>
          <div className="branch-tree-canvas">
            {rootNodes.length > 0 ? (
              rootNodes.map((rootNode) => renderTreeNode(rootNode))
            ) : (
              <p className="empty-text">No future selves generated yet.</p>
            )}
          </div>
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
    </section>
  );
}
