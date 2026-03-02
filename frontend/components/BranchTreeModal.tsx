"use client";

import { useEffect, useMemo } from "react";
import { AvatarPlaceholder } from "@/components/AvatarPlaceholder";
import type { SelfCard } from "@/lib/types";

interface BranchTreeModalProps {
  isOpen: boolean;
  title?: string;
  futureSelves: SelfCard[];
  activeSelfId: string | null;
  onSelectSelf: (selfId: string) => void;
  onClose: () => void;
}

export function BranchTreeModal({
  isOpen,
  title = "Branch Tree",
  futureSelves,
  activeSelfId,
  onSelectSelf,
  onClose,
}: BranchTreeModalProps) {
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
      const parentId = selfCard.parentSelfId ?? "__root__";
      const list = map.get(parentId) ?? [];
      list.push(selfCard);
      map.set(parentId, list);
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

  const activePathIds = useMemo(() => {
    if (!activeSelfId) {
      return new Set<string>();
    }
    const path = new Set<string>();
    const seen = new Set<string>();
    let cursor = byId.get(activeSelfId) ?? null;

    while (cursor && !seen.has(cursor.id)) {
      path.add(cursor.id);
      seen.add(cursor.id);
      cursor = cursor.parentSelfId ? byId.get(cursor.parentSelfId) ?? null : null;
    }

    return path;
  }, [activeSelfId, byId]);

  const activePath = useMemo(() => {
    if (!activeSelfId) {
      return [] as SelfCard[];
    }
    const path: SelfCard[] = [];
    const seen = new Set<string>();
    let cursor = byId.get(activeSelfId) ?? null;

    while (cursor && !seen.has(cursor.id)) {
      path.push(cursor);
      seen.add(cursor.id);
      cursor = cursor.parentSelfId ? byId.get(cursor.parentSelfId) ?? null : null;
    }

    path.reverse();
    return path;
  }, [activeSelfId, byId]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpen, onClose]);

  const renderNode = (selfCard: SelfCard) => {
    const children = childrenByParent.get(selfCard.id) ?? [];
    const isActive = activeSelfId === selfCard.id;
    const isOnActivePath = activePathIds.has(selfCard.id);

    return (
      <div key={selfCard.id} className="tree-list-item">
        <div className="tree-list-row">
        <button
          type="button"
          className={[
            "tree-avatar-node",
            isOnActivePath ? "tree-avatar-path" : "",
            isActive ? "tree-avatar-active" : "",
          ].join(" ").trim()}
          onClick={() => {
            onSelectSelf(selfCard.id);
            onClose();
          }}
          aria-label={selfCard.name}
        >
          {selfCard.avatarUrl ? (
            <img src={selfCard.avatarUrl} alt={selfCard.name} className="tree-avatar-image" />
          ) : (
            <AvatarPlaceholder
              name={selfCard.name}
              primaryColor={selfCard.visualStyle.primaryColor}
              accentColor={selfCard.visualStyle.accentColor}
            />
          )}
          <span className="tree-avatar-tooltip">{selfCard.name}</span>
        </button>
        </div>

        {children.length > 0 ? (
          <div className="tree-list-children">
            {children.map((child) => renderNode(child))}
          </div>
        ) : null}
      </div>
    );
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="branch-tree-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
    >
      <div className="branch-tree-modal" onClick={(event) => event.stopPropagation()}>
        <div className="branch-tree-modal-header">
          <div>
            <p className="eyebrow">Node Map</p>
            <h3>{title}</h3>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>

        <p className="branch-tree-modal-hint">
          Hover an avatar to see its name. Click a node to jump to that branch.
        </p>

        {activePath.length > 0 ? (
          <div className="path-chip-row">
            {activePath.map((node) => (
              <span
                key={node.id}
                className={activeSelfId === node.id ? "path-chip path-chip-active" : "path-chip"}
              >
                {node.name}
              </span>
            ))}
          </div>
        ) : null}

        <div className="branch-tree-modal-canvas">
          {rootNodes.length > 0 ? (
            rootNodes.map((rootNode) => renderNode(rootNode))
          ) : (
            <p className="empty-text">No future nodes yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
