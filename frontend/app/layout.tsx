import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Future Selves Prototype",
  description: "Frontend-only prototype for interview, profile reveal, and future self conversation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
