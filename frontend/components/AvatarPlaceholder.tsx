interface AvatarPlaceholderProps {
  name: string;
  primaryColor: string;
  accentColor: string;
}

function initialsFromName(name: string): string {
  const parts = name
    .split(" ")
    .map((part) => part.trim())
    .filter(Boolean);

  if (parts.length === 0) {
    return "FS";
  }

  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function AvatarPlaceholder({ name, primaryColor, accentColor }: AvatarPlaceholderProps) {
  return (
    <div
      className="avatar-placeholder"
      style={{
        background: `radial-gradient(circle at 30% 25%, ${accentColor}, ${primaryColor})`,
      }}
      aria-label={`${name} avatar placeholder`}
    >
      <span>{initialsFromName(name)}</span>
    </div>
  );
}
