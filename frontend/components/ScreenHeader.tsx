interface ScreenHeaderProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
}

export function ScreenHeader({ eyebrow, title, subtitle }: ScreenHeaderProps) {
  return (
    <header className="screen-header">
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      <h1>{title}</h1>
      {subtitle ? <p className="subtitle">{subtitle}</p> : null}
    </header>
  );
}
