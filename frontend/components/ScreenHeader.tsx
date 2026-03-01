interface ScreenHeaderProps {
  eyebrow: string;
  title: string;
  subtitle: string;
}

export default function ScreenHeader({ eyebrow, title, subtitle }: ScreenHeaderProps) {
  return (
    <header className="screen-header">
      <p className="screen-header__eyebrow">{eyebrow}</p>
      <h1 className="screen-header__title">{title}</h1>
      <p className="screen-header__subtitle">{subtitle}</p>
    </header>
  );
}
