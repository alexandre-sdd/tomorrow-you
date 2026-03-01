import { SelfCard } from "../lib/types";
import AvatarPlaceholder from "./AvatarPlaceholder";

interface SelfCardPanelProps {
  selfCard: SelfCard;
}

export default function SelfCardPanel({ selfCard }: SelfCardPanelProps) {
  return (
    <aside className="self-card-panel">
      <div className="self-card-panel__avatar-wrap">
        <AvatarPlaceholder
          name={selfCard.name}
          primaryColor={selfCard.visualStyle.primaryColor}
          accentColor={selfCard.visualStyle.accentColor}
          glowIntensity={selfCard.visualStyle.glowIntensity}
        />
      </div>
      <div className="self-card-panel__meta">
        <p className="self-card-panel__label">Future Persona</p>
        <h2>{selfCard.name}</h2>
        <p>{selfCard.optimizationGoal}</p>
      </div>
      <div className="self-card-panel__grid">
        <div>
          <h3>Worldview</h3>
          <p>{selfCard.worldview}</p>
        </div>
        <div>
          <h3>Core Belief</h3>
          <p>{selfCard.coreBelief}</p>
        </div>
        <div>
          <h3>Trade-off</h3>
          <p>{selfCard.tradeOff}</p>
        </div>
      </div>
    </aside>
  );
}
