"use client";

import { useMemo, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { InputBar } from "@/components/InputBar";
import { ScreenHeader } from "@/components/ScreenHeader";
import { SelfCardPanel } from "@/components/SelfCardPanel";
import type { SelfCard } from "@/lib/types";
import type { ConversationHistoryMessage } from "@/lib/api";
import { getTimeHorizonLabel } from "@/lib/timeHorizon";

interface ConversationScreenProps {
  sessionId: string;
  futureSelves: SelfCard[];
  activeSelfId: string;
  historiesBySelf: Record<string, ConversationHistoryMessage[]>;
  isSendingMessage: boolean;
  isBranching: boolean;
  isRecording: boolean;
  isTranscribing: boolean;
  isSynthesizing: boolean;
  isPlaying: boolean;
  canReplayLastAudio: boolean;
  onChangeSelf: (selfId: string) => void;
  onSendMessage: (message: string) => Promise<void>;
  onBranch: (numFutures: number) => Promise<void>;
  onStartRecording: () => Promise<void>;
  onStopRecording: () => Promise<void>;
  onReplayLastAudio: () => Promise<void>;
  onBackToSelection: () => void;
}

export function ConversationScreen({
  sessionId,
  futureSelves,
  activeSelfId,
  historiesBySelf,
  isSendingMessage,
  isBranching,
  isRecording,
  isTranscribing,
  isSynthesizing,
  isPlaying,
  canReplayLastAudio,
  onChangeSelf,
  onSendMessage,
  onBranch,
  onStartRecording,
  onStopRecording,
  onReplayLastAudio,
  onBackToSelection,
}: ConversationScreenProps) {
  const [branchCount, setBranchCount] = useState(3);

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

  const activeSelf = useMemo(
    () => futureSelves.find((selfCard) => selfCard.id === activeSelfId) ?? null,
    [futureSelves, activeSelfId],
  );

  const messages = useMemo(() => {
    const history = historiesBySelf[activeSelfId] || [];
    return history.map((entry, index) => ({
      id: `${activeSelfId}_${entry.role}_${index}`,
      role: entry.role,
      content: entry.content,
    }));
  }, [activeSelfId, historiesBySelf]);

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

  const parentSelf = useMemo(
    () => (activeSelf?.parentSelfId ? byId.get(activeSelf.parentSelfId) ?? null : null),
    [activeSelf, byId],
  );

  const activeChildren = useMemo(
    () => (activeSelf ? childrenByParent.get(activeSelf.id) ?? [] : []),
    [activeSelf, childrenByParent],
  );

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

  const horizonLabel = activeSelf ? getTimeHorizonLabel(activeSelf.depthLevel) : "Present";
  const isVoiceBusy = isTranscribing || isSynthesizing;
  const inputDisabled = isSendingMessage || isBranching || isVoiceBusy || isRecording;
  const recordButtonLabel = isRecording ? "■" : "🎙";
  const recordButtonTitle = isRecording ? "Release to stop" : "Hold to talk";
  const voiceStatus = isRecording
    ? "Recording..."
    : isTranscribing
      ? "Transcribing..."
      : isSynthesizing
        ? "Synthesizing reply..."
        : isPlaying
          ? "Playing reply..."
          : "Voice ready";

  const renderTreeNode = (selfCard: SelfCard) => {
    const children = childrenByParent.get(selfCard.id) ?? [];
    const isActive = activeSelfId === selfCard.id;
    const isOnActivePath = activePathIds.has(selfCard.id);
    const descendantCount = descendantCountById.get(selfCard.id) ?? 0;
    const selfHorizonLabel = getTimeHorizonLabel(selfCard.depthLevel);

    return (
      <article key={selfCard.id} className="tree-node-wrap">
        <button
          type="button"
          className={[
            "tree-node",
            isOnActivePath ? "tree-node-path" : "",
            isActive ? "tree-node-active" : "",
          ].join(" ").trim()}
          onClick={() => onChangeSelf(selfCard.id)}
        >
          <span className="tree-node-name">{selfCard.name}</span>
          <span className="tree-node-meta">Depth {selfCard.depthLevel} · {selfHorizonLabel}</span>
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

  if (!activeSelf) {
    return (
      <section className="stack-screen">
        <ScreenHeader
          title="No active self selected"
          subtitle="Select a self from the list to continue."
        />
        <button type="button" onClick={onBackToSelection}>
          Back to selection
        </button>
      </section>
    );
  }

  return (
    <section className="conversation-layout">
      <aside className="surface-card conversation-sidebar">
        <p className="eyebrow">Session {sessionId}</p>
        <h2>Node Navigator</h2>
        <div className="path-chip-row">
          {activePath.map((node) => (
            <button
              key={node.id}
              type="button"
              className={activeSelfId === node.id ? "path-chip path-chip-active" : "path-chip"}
              onClick={() => onChangeSelf(node.id)}
            >
              {node.name}
            </button>
          ))}
        </div>
        <div className="sidebar-node-actions">
          <button
            type="button"
            className="ghost-button"
            onClick={() => parentSelf && onChangeSelf(parentSelf.id)}
            disabled={!parentSelf}
          >
            Go to parent
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              if (activeChildren.length > 0) {
                onChangeSelf(activeChildren[0].id);
              }
            }}
            disabled={activeChildren.length === 0}
          >
            Go to first child
          </button>
        </div>
        <div className="branch-tree-canvas conversation-tree-canvas">
          {rootNodes.length > 0 ? (
            rootNodes.map((rootNode) => renderTreeNode(rootNode))
          ) : (
            <p className="empty-text">No conversation nodes yet.</p>
          )}
        </div>
        <SelfCardPanel
          selfCard={activeSelf}
          isActive
          onClick={() => onChangeSelf(activeSelf.id)}
        />
        <button type="button" className="ghost-button" onClick={onBackToSelection}>
          Back to selection
        </button>
      </aside>

      <section className="stack-screen conversation-main">
        <ScreenHeader
          eyebrow="Conversation"
          title={activeSelf.name}
          subtitle={`${activeSelf.toneOfVoice} · ${horizonLabel}`}
        />

        <div className="surface-card status-card branch-row">
          <label>
            Branch count
            <select
              value={branchCount}
              onChange={(event) => setBranchCount(Number(event.target.value))}
              disabled={isBranching}
            >
              <option value={2}>2</option>
              <option value={3}>3</option>
              <option value={4}>4</option>
              <option value={5}>5</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() => onBranch(branchCount)}
            disabled={isBranching || isSendingMessage}
          >
            {isBranching ? "Branching..." : "Branch from this conversation"}
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={onReplayLastAudio}
            disabled={!canReplayLastAudio || isRecording || isTranscribing}
          >
            Play last reply
          </button>
          <p className="voice-status">{voiceStatus}</p>
        </div>

        <ChatPanel
          messages={messages}
          emptyText="Start talking to this future self."
        />

        <InputBar
          placeholder="Ask your future self..."
          submitLabel={isSendingMessage ? "Sending..." : "Send"}
          disabled={inputDisabled}
          secondaryActionLabel={recordButtonLabel}
          secondaryActionTitle={recordButtonTitle}
          secondaryActionClassName={isRecording ? "recording-button icon-button" : "ghost-button icon-button"}
          secondaryActionDisabled={isSendingMessage || isBranching || isVoiceBusy}
          onSecondaryActionPressStart={onStartRecording}
          onSecondaryActionPressEnd={onStopRecording}
          onSubmit={onSendMessage}
        />
      </section>
    </section>
  );
}
