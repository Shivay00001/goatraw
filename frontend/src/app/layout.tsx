import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GoatRaw — Autonomous AI Agent Platform",
  description: "Production-grade AI agents for business automation. Lead gen, research, monitoring, and more.",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
