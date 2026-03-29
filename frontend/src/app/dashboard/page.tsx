"use client";
import { useState } from "react";
import { PageHeader, PageContent } from "@/components/layout/AppShell";
import { Card, CardHeader, StatCard, StatusBadge, AgentTypeBadge, CodeBlock, Icon, ICONS, Spinner, SkeletonRow } from "@/components/ui";
import { useRunAgent, useUsage } from "@/hooks";
import { useRecentTasks, useUser } from "@/store";
import type { AgentType } from "@/types";

const AGENT_OPTIONS: { value: AgentType; label: string; desc: string }[] = [
  { value: "auto",                label: "⚡ Auto Route",     desc: "AI picks best agent" },
  { value: "lead_generation",     label: "🎯 Lead Gen",       desc: "Find B2B leads" },
  { value: "market_research",     label: "📊 Research",       desc: "Market intelligence" },
  { value: "competitor_analysis", label: "🔍 Competitor",     desc: "Competitive intel" },
  { value: "data_extraction",     label: "📋 Data Extract",   desc: "Scrape & structure" },
  { value: "outreach_drafting",   label: "✉️ Outreach",       desc: "Draft cold emails" },
  { value: "website_audit",       label: "🔎 Audit",          desc: "SEO & copy review" },
  { value: "monitoring",          label: "👁 Monitor",        desc: "Track changes" },
];

export default function DashboardPage() {
  const [goal, setGoal] = useState("");
  const [agentType, setAgentType] = useState<AgentType>("auto");
  const { run, loading, status } = useRunAgent();
  const [lastResult, setLastResult] = useState<unknown>(null);
  const recentTasks = useRecentTasks();
  const user = useUser();
  const { current: usage, limits } = useUsage();

  const handleRun = async () => {
    if (!goal.trim()) return;
    const result = await run(goal.trim(), agentType);
    if (result) setLastResult(result);
    setGoal("");
  };

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle={`Welcome back, ${user?.full_name?.split(" ")[0] ?? "there"}`}
        action={
          <span className="badge">
            <span className="w-1.5 h-1.5 rounded-full bg-green dot-pulse" />
            API Online
          </span>
        }
      />
      <PageContent>
        {/* Stats row */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard
            value={usage?.usage.tasks_completed ?? "—"}
            label="Tasks This Month"
            delta={`${limits?.current.tasks_this_month ?? 0} / ${limits?.limits.tasks_per_month === -1 ? "∞" : limits?.limits.tasks_per_month ?? "—"} used`}
            icon="⚡"
          />
          <StatCard
            value={usage?.usage.steps_executed ?? "—"}
            label="Steps Executed"
            delta="avg 11 per task"
            icon="🔧"
          />
          <StatCard
            value={`$${usage?.usage.estimated_cost_usd?.toFixed(4) ?? "0.00"}`}
            label="Estimated Cost"
            delta={`Plan: ${user?.plan?.toUpperCase() ?? "FREE"}`}
            icon="💰"
          />
        </div>

        {/* Command box */}
        <div className="card border-border2 mb-6 focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/20 transition-all">
          <div className="flex items-center gap-2 mb-3">
            <Icon d={ICONS.terminal.d} size={13} className="text-muted" />
            <span className="section-label">NEW AGENT TASK</span>
          </div>
          <textarea
            className="w-full bg-transparent border-none outline-none text-text text-[15px] resize-none leading-relaxed placeholder:text-muted"
            rows={3}
            placeholder="Describe what you need the agent to do...&#10;e.g. 'Find 20 real estate agencies in Mumbai, extract emails and phone numbers'"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleRun(); }}
          />
          <div className="flex items-center gap-2 pt-3 border-t border-border mt-3">
            <select
              className="bg-surface2 border border-border2 text-text rounded-lg px-2.5 py-1.5 text-xs font-medium outline-none cursor-pointer"
              value={agentType}
              onChange={(e) => setAgentType(e.target.value as AgentType)}
            >
              {AGENT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <span className="text-[11px] text-muted ml-1">⌘+Enter to run</span>
            <button
              className="btn btn-primary ml-auto"
              onClick={handleRun}
              disabled={loading || !goal.trim()}
            >
              {loading ? <Spinner size={14} /> : <Icon d={ICONS.send.d} size={14} />}
              {loading ? `${status}...` : "Run Agent"}
            </button>
          </div>
        </div>

        {/* Last result */}
        {lastResult && (
          <div className="mb-6 animate-fade-in">
            <div className="flex items-center gap-2 mb-2">
              <span className="badge badge-green">✓ Result</span>
            </div>
            <CodeBlock
              code={JSON.stringify((lastResult as { output?: unknown }).output ?? lastResult, null, 2)}
              language="json"
            />
          </div>
        )}

        {/* Recent tasks */}
        <Card>
          <CardHeader title="Recent Tasks" subtitle="Your last 20 agent executions" />
          {recentTasks.length === 0 ? (
            <div className="py-10 text-center text-muted text-sm">
              No tasks yet. Run your first agent above ↑
            </div>
          ) : (
            recentTasks.map((task) => (
              <div key={task.id} className="flex items-center gap-3 py-2.5 border-b border-border last:border-0 hover:bg-surface2/50 -mx-4 px-4 rounded transition-colors">
                <StatusBadge status={task.status} />
                <span className="flex-1 text-[13px] text-text truncate">{task.goal}</span>
                <AgentTypeBadge type={task.agentType} />
                <span className="text-[11px] text-muted font-mono hidden md:block">
                  {new Date(task.createdAt).toLocaleTimeString()}
                </span>
                <span className="text-[10px] font-mono text-muted/50">#{task.id.slice(0, 8)}</span>
              </div>
            ))
          )}
        </Card>
      </PageContent>
    </>
  );
}
