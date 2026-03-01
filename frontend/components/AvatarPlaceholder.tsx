interface AvatarPlaceholderProps {
  name: string;
  primaryColor: string;
  accentColor: string;
  glowIntensity: number;
}

export default function AvatarPlaceholder({
  name,
  primaryColor,
  accentColor,
  glowIntensity,
}: AvatarPlaceholderProps) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((chunk) => chunk[0]?.toUpperCase())
    .join("");

  return (
    <div
      className="avatar-placeholder"
      style={{
        background: `radial-gradient(circle at 30% 25%, ${accentColor}88, ${primaryColor}55 64%, #f2efec 100%)`,
        boxShadow: `0 0 0 1px rgba(0,0,0,0.08), 0 14px 40px rgba(0,0,0,${0.15 + glowIntensity * 0.2})`,
      }}
      aria-label={`${name} avatar placeholder`}
    >
      <span>{initials}</span>
    </div>
  );
}
