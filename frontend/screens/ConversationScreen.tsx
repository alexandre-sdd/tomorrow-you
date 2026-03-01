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
  onChangeSelf: (selfId: string) => void;
  onSendMessage: (message: string) => Promise<void>;
  onBranch: (numFutures: number) => Promise<void>;
  onBackToSelection: () => void;
}

export function ConversationScreen({
  sessionId,
  futureSelves,
  activeSelfId,
  historiesBySelf,
  isSendingMessage,
  isBranching,
  onChangeSelf,
  onSendMessage,
  onBranch,
  onBackToSelection,
}: ConversationScreenProps) {
  const [branchCount, setBranchCount] = useState(3);

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

  const horizonLabel = activeSelf ? getTimeHorizonLabel(activeSelf.depthLevel) : "Present";

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
        <h2>Future Selves</h2>
        <div className="sidebar-list">
          {futureSelves.map((selfCard) => (
            <SelfCardPanel
              key={selfCard.id}
              selfCard={selfCard}
              isActive={selfCard.id === activeSelfId}
              onClick={() => onChangeSelf(selfCard.id)}
            />
          ))}
        </div>
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
        </div>

        <ChatPanel
          messages={messages}
          emptyText="Start talking to this future self."
        />

        <InputBar
          placeholder="Ask your future self..."
          submitLabel={isSendingMessage ? "Sending..." : "Send"}
          disabled={isSendingMessage || isBranching}
          onSubmit={onSendMessage}
        />
      </section>
    </section>
  );
}
