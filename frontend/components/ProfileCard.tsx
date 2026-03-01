import { UserProfile } from "../lib/types";

interface ProfileCardProps {
  profile: UserProfile;
}

function Section({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="profile-card__section">
      <h3>{title}</h3>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export default function ProfileCard({ profile }: ProfileCardProps) {
  return (
    <article className="profile-card">
      <p className="profile-card__id">{profile.id}</p>
      <Section title="Core Values" items={profile.coreValues} />
      <Section title="Fears" items={profile.fears} />
      <Section title="Hidden Tensions" items={profile.hiddenTensions} />
      <section className="profile-card__section">
        <h3>Decision Style</h3>
        <p>{profile.decisionStyle}</p>
      </section>
      <section className="profile-card__section">
        <h3>Self Narrative</h3>
        <p>{profile.selfNarrative}</p>
      </section>
      <section className="profile-card__section">
        <h3>Current Dilemma</h3>
        <p>{profile.currentDilemma}</p>
      </section>
    </article>
  );
}
