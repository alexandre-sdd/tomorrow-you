import type { UserProfile } from "@/lib/types";

interface ProfileCardProps {
  profile: UserProfile;
}

function ListSection({ title, values }: { title: string; values: string[] }) {
  return (
    <section className="info-section">
      <h3>{title}</h3>
      <ul>
        {values.map((value) => (
          <li key={value}>{value}</li>
        ))}
      </ul>
    </section>
  );
}

export function ProfileCard({ profile }: ProfileCardProps) {
  return (
    <article className="surface-card profile-card">
      <h2>Profile Snapshot</h2>
      <p className="profile-dilemma">{profile.currentDilemma}</p>

      <div className="info-grid">
        <ListSection title="Core Values" values={profile.coreValues} />
        <ListSection title="Fears" values={profile.fears} />
        <ListSection title="Hidden Tensions" values={profile.hiddenTensions} />
      </div>

      <section className="info-section">
        <h3>Decision Style</h3>
        <p>{profile.decisionStyle}</p>
      </section>

      <section className="info-section">
        <h3>Self Narrative</h3>
        <p>{profile.selfNarrative}</p>
      </section>
    </article>
  );
}
