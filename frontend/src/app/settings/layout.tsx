import { AppShell } from "@/components/layout/AppShell";
import type { ReactNode } from "react";
// Shared layout wrapping all dashboard-style pages
export default function Layout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
