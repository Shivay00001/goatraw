"use client";
/**
 * GoatRaw — Shared UI Components
 */

import { type ReactNode, useState } from "react";
import type { TaskStatus, AgentType } from "@/types";
import { clsx } from "clsx";

// ── Icons (inline SVG) ────────────────────────────────────────
interface IconProps { className?: string; size?: number }
const i = (d: string) => ({ d });

export const ICONS = {
  terminal:   i("M4 17l6-6-6-6M12 19h8"),
  brain:      i("M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588 4 4 0 0 0 7.636 2.106A3.5 3.5 0 0 0 17 16h.5a4 4 0 0 0 3.168-6.397A3.5 3.5 0 0 0 12 5Z"),
  zap:        i("M13 2L3 14h9l-1 8 10-12h-9l1-8z"),
  clock:      i("M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm0 5v5l3 3"),
  check:      i("M20 6L9 17l-5-5"),
  x:          i("M18 6L6 18M6 6l12 12"),
  plus:       i("M12 5v14M5 12h14"),
  send:       i("M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"),
  loader:     i("M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"),
  trash:      i("M3 6h18M8 6V4h8v2M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"),
  edit:       i("M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"),
  copy:       i("M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-4-4H8zM14 2v6h6"),
  eye:        i("M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"),
  refresh:    i("M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"),
  chevronDown:i("M6 9l6 6 6-6"),
  chevronRight:i("M9 18l6-6-6-6"),
  arrowRight: i("M5 12h14M12 5l7 7-7 7"),
  settings:   i("M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"),
  user:       i("M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"),
  logout:     i("M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"),
  star:       i("M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"),
  link:       i("M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"),
  key:        i("M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"),
};

export function Icon({ d, size = 16, className = "" }: { d: string; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
      className={className}>
      <path d={d} />
    </svg>
  );
}

// ── Spinner ───────────────────────────────────────────────────
export function Spinner({ size = 16, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round"
      className={clsx("animate-spin", className)}>
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  );
}

// ── StatusBadge ───────────────────────────────────────────────
const STATUS_MAP: Record<TaskStatus, { label: string; cls: string; dot: string }> = {
  queued:    { label: "queued",    cls: "bg-yellow/10 text-yellow border-yellow/20",   dot: "bg-yellow dot-pulse" },
  planning:  { label: "planning",  cls: "bg-blue/10 text-blue border-blue/20",         dot: "bg-blue dot-pulse" },
  executing: { label: "running",   cls: "bg-accent/10 text-accent2 border-accent/20",  dot: "bg-accent dot-pulse" },
  completed: { label: "done",      cls: "bg-green/10 text-green border-green/20",      dot: "bg-green" },
  failed:    { label: "failed",    cls: "bg-red/10 text-red border-red/20",            dot: "bg-red" },
  cancelled: { label: "cancelled", cls: "bg-surface2 text-muted border-border",        dot: "bg-muted" },
};

export function StatusBadge({ status }: { status: TaskStatus }) {
  const s = STATUS_MAP[status] ?? STATUS_MAP.queued;
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-mono border", s.cls)}>
      <span className={clsx("w-1.5 h-1.5 rounded-full flex-shrink-0", s.dot)} />
      {s.label}
    </span>
  );
}

// ── AgentTypeBadge ────────────────────────────────────────────
const AGENT_LABELS: Record<string, string> = {
  lead_generation: "Lead Gen", market_research: "Research",
  competitor_analysis: "Competitor", data_extraction: "Data Extract",
  outreach_drafting: "Outreach", website_audit: "Audit",
  monitoring: "Monitor", general: "General", auto: "Auto",
};

export function AgentTypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono bg-surface2 text-muted border border-border">
      {AGENT_LABELS[type] ?? type}
    </span>
  );
}

// ── Card ──────────────────────────────────────────────────────
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={clsx("card", className)}>{children}</div>;
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h3 className="text-[13.5px] font-semibold text-text">{title}</h3>
        {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

// ── Stat Card ─────────────────────────────────────────────────
export function StatCard({ value, label, delta, icon }: { value: string | number; label: string; delta?: string; icon?: string }) {
  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-2xl font-bold font-mono text-accent2">{value}</div>
          <div className="text-xs text-muted mt-1">{label}</div>
          {delta && <div className="text-[11px] text-green font-mono mt-1">{delta}</div>}
        </div>
        {icon && <span className="text-2xl opacity-60">{icon}</span>}
      </div>
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────
export function EmptyState({ icon, title, description, action }: {
  icon: string; title: string; description?: string; action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
      <div className="text-4xl opacity-40">{icon}</div>
      <div className="text-sm font-semibold text-text2">{title}</div>
      {description && <div className="text-xs text-muted max-w-xs">{description}</div>}
      {action}
    </div>
  );
}

// ── Code Block ────────────────────────────────────────────────
export function CodeBlock({ code, language = "json" }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  return (
    <div className="relative rounded-lg border border-border2 bg-surface2 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border">
        <span className="text-[10px] font-mono text-muted">{language}</span>
        <button onClick={copy} className="text-[10px] font-mono text-muted hover:text-accent2 transition-colors">
          {copied ? "✓ copied" : "copy"}
        </button>
      </div>
      <pre className="p-3 text-xs font-mono text-accent2 overflow-x-auto whitespace-pre-wrap max-h-64">
        {code}
      </pre>
    </div>
  );
}

// ── Input ─────────────────────────────────────────────────────
export function Input({ label, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-xs font-medium text-text2">{label}</label>}
      <input className="input" {...props} />
    </div>
  );
}

// ── Toggle ────────────────────────────────────────────────────
export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <div className="flex items-center gap-2 cursor-pointer" onClick={() => onChange(!checked)}>
      <div className={clsx(
        "w-8 h-4 rounded-full transition-colors duration-200 relative",
        checked ? "bg-accent" : "bg-border2"
      )}>
        <div className={clsx(
          "absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200",
          checked ? "translate-x-4" : "translate-x-0.5"
        )} />
      </div>
      {label && <span className="text-xs text-text2">{label}</span>}
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)" }}
      onClick={onClose}>
      <div className="bg-surface border border-border2 rounded-2xl p-6 w-full max-w-md animate-slide-up"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold">{title}</h2>
          <button onClick={onClose} className="btn-ghost p-1 rounded-lg">
            <Icon d={ICONS.x.d} size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ── Notification Toast ────────────────────────────────────────
export function NotificationToasts() {
  const notifications = useStore((s) => s.notifications);
  const remove = useStore((s) => s.removeNotification);

  const colors = { success: "border-green/30 bg-green/10 text-green", error: "border-red/30 bg-red/10 text-red", info: "border-accent/30 bg-accent/10 text-accent2" };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {notifications.map((n) => (
        <div key={n.id} className={clsx(
          "flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium animate-fade-in shadow-lg",
          colors[n.type]
        )}>
          <span>{n.message}</span>
          <button onClick={() => remove(n.id)} className="ml-1 opacity-60 hover:opacity-100">
            <Icon d={ICONS.x.d} size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}

// ── Skeleton loaders ──────────────────────────────────────────
export function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 py-3 border-b border-border">
      <div className="skeleton w-2 h-2 rounded-full" />
      <div className="skeleton flex-1 h-3" />
      <div className="skeleton w-16 h-3" />
      <div className="skeleton w-10 h-3" />
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="card space-y-3">
      <div className="skeleton w-24 h-4" />
      <div className="skeleton w-full h-3" />
      <div className="skeleton w-3/4 h-3" />
    </div>
  );
}
