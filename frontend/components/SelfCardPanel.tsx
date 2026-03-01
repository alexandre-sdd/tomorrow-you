import { AvatarPlaceholder } from "./AvatarPlaceholder";
import clsx from "./clsx";
import type { SelfCard } from "@/lib/types";
import { getTimeHorizonLabel } from "@/lib/timeHorizon";

interface SelfCardPanelProps {
  selfCard: SelfCard;
  isActive?: boolean;
  onClick?: () => void;
}

export function SelfCardPanel({ selfCard, isActive, onClick }: SelfCardPanelProps) {
  const horizonLabel = getTimeHorizonLabel(selfCard.depthLevel);

  return (
    <button
      type="button"
      className={clsx("self-card", isActive ? "self-card-active" : "")}
      onClick={onClick}
    >
      <div className="self-card-top">
        {selfCard.avatarUrl ? (
          <img
            src={selfCard.avatarUrl}
            alt={selfCard.name}
            className="avatar-image"
          />
        ) : (
          <AvatarPlaceholder
            name={selfCard.name}
            primaryColor={selfCard.visualStyle.primaryColor}
            accentColor={selfCard.visualStyle.accentColor}
          />
        )}
        <div>
          <h3>{selfCard.name}</h3>
          <p className="self-meta">
            Depth {selfCard.depthLevel} · {horizonLabel}
          </p>
        </div>
      </div>
      <p>{selfCard.optimizationGoal}</p>
      <p className="self-tradeoff">Trade-off: {selfCard.tradeOff}</p>
    </button>
  );
}
