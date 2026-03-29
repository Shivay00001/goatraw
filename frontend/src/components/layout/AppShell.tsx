"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { Icon, ICONS, NotificationToasts } from "@/components/ui";
import { useStore, useUser, useNotify } from "@/store";
import type { ReactNode } from "react";

const NAV = [
  { href: "/dashboard",  label: "Dashboard",  icon: ICONS.terminal.d },
  { href: "/tasks",      label: "Tasks",       icon: ICONS.clock.d },
  { section: "AGENT SYSTEM" },
  { href: "/skills",     label: "Skills",      icon: ICONS.star.d },
  { href: "/memory",     label: "Memory",      icon: ICONS.brain.d },
  { section: "AUTOMATION" },
  { href: "/heartbeat",  label: "Heartbeat",   icon: ICONS.zap.d },
  { href: "/cron",       label: "Schedules",   icon: ICONS.clock.d },
  { section: "CHANNELS" },
  { href: "/channels",   label: "Channels",    icon: ICONS.link.d },
  { section: "ACCOUNT" },
  { href: "/upgrade",    label: "Upgrade",     icon: ICONS.zap.d },
  { href: "/api-docs",   label: "API Docs",    icon: ICONS.link.d },
  { href: "/settings",   label: "Settings",    icon: ICONS.settings.d },
];

const PLAN_COLORS: Record<string, string> = {
  free: "text-muted",
  pro: "text-accent2",
  enterprise: "text-yellow",
};

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const user = useUser();
  const logout = useStore((s) => s.logout);

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* Sidebar */}
      <aside className="w-[220px] min-w-[220px] flex flex-col border-r border-border bg-surface">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-5 border-b border-border">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center text-base">
            🦅
          </div>
          <span className="font-mono font-bold text-lg text-accent2 tracking-tight">GoatRaw</span>
          <span className="ml-auto text-[9px] font-mono text-muted border border-border2 rounded px-1">v2</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-3 px-2 overflow-y-auto">
          {NAV.map((item, i) => {
            if ("section" in item) {
              return (
                <div key={i} className="section-label px-2 pt-4 pb-1.5">{item.section}</div>
              );
            }
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link key={item.href} href={item.href!}
                className={clsx(
                  "flex items-center gap-2.5 px-2.5 py-2 rounded-lg mb-0.5 text-[13px] font-medium transition-all duration-100",
                  active
                    ? "bg-accent/10 text-accent2 border border-accent/20"
                    : "text-muted hover:bg-surface2 hover:text-text"
                )}>
                <Icon d={item.icon!} size={14} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User */}
        <div className="p-3 border-t border-border">
          <div className="flex items-center gap-2.5 p-2 rounded-lg bg-surface2">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-accent to-purple-400 flex items-center justify-center text-[11px] font-bold text-white font-mono">
              {user?.full_name?.[0]?.toUpperCase() ?? user?.email?.[0]?.toUpperCase() ?? "?"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[12.5px] font-semibold text-text truncate">
                {user?.full_name ?? user?.email ?? "User"}
              </div>
              <div className={clsx("text-[10px] font-mono uppercase", PLAN_COLORS[user?.plan ?? "free"])}>
                {user?.plan ?? "free"} plan
              </div>
            </div>
            <button onClick={logout} className="text-muted hover:text-red transition-colors p-0.5" title="Sign out">
              <Icon d={ICONS.logout.d} size={13} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {children}
      </main>

      <NotificationToasts />
    </div>
  );
}

export function PageHeader({ title, subtitle, action }: {
  title: string; subtitle?: string; action?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between h-[52px] px-6 border-b border-border bg-surface shrink-0">
      <div className="flex items-center gap-3">
        <h1 className="text-[15px] font-semibold">{title}</h1>
        {subtitle && <span className="text-xs text-muted hidden sm:block">{subtitle}</span>}
      </div>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </div>
  );
}

export function PageContent({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx("flex-1 overflow-y-auto p-6", className)}>
      {children}
    </div>
  );
}
