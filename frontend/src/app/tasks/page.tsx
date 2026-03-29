"use client";
import { useState } from "react";
import { PageHeader, PageContent } from "@/components/layout/AppShell";
import {
  Card, CardHeader, StatusBadge, AgentTypeBadge,
  Icon, ICONS, Spinner, CodeBlock, EmptyState, SkeletonRow,
} from "@/components/ui";
import { useRunAgent } from "@/hooks";
import { useRecentTasks } from "@/store";
import { tasksApi } from "@/services/api";
import { clsx } from "clsx";
import type { TaskResult, AgentType } from "@/types";

function TaskDetail({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const [result, setResult] = useState<TaskResult | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch once on mount
  useState(() => {
    tasksApi.get(taskId).then((r) => {
      if (r.result) setResult(r.result);
      setLoading(false);
    });
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.8)", backdropFilter: "blur(4px)" }}
      onClick={onClose}>
      <div className="bg-surface border border-border2 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col animate-slide-up"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <span className="font-semibold">Task Detail</span>
          <button className="btn btn-ghost p-1.5" onClick={onClose}>
            <Icon d={ICONS.x.d} size={14} />
          </button>
        </div>
        <div className="overflow-y-auto p-5">
          {loading ? (
            <div className="flex items-center gap-2 text-muted text-sm">
              <Spinner size={14} /> Loading...
            </div>
          ) : result ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <StatusBadge status={result.status} />
                <AgentTypeBadge type={result.agent_type} />
                <span className="font-mono text-[10px] text-muted ml-auto">#{result.task_id.slice(0, 8)}</span>
              </div>
              <p className="text-sm text-text2">{result.goal}</p>
              {result.output && (
                <div>
                  <div className="section-label mb-2">Output</div>
                  <CodeBlock code={JSON.stringify(result.output, null, 2)} language="json" />
                </div>
              )}
              {result.error && (
                <div className="p-3 rounded-lg bg-red/5 border border-red/20 text-sm text-red">
                  Error: {result.error}
                </div>
              )}
              <div className="flex gap-4 text-[11px] font-mono text-muted">
                <span>Steps: {result.steps_taken}</span>
                <span>Completed: {result.completed_at ? new Date(result.completed_at).toLocaleString() : "—"}</span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted">No result data available.</p>
          )}
        </div>
      </div>
    </div>
  );
}

const QUICK_TASKS = [
  { goal: "Find 10 SaaS companies in Bangalore hiring developers", type: "lead_generation" as AgentType },
  { goal: "Research the AI CRM market: top 5 players, pricing, trends", type: "market_research" as AgentType },
  { goal: "Audit the homepage of notion.so for SEO and conversion issues", type: "website_audit" as AgentType },
  { goal: "Find top 5 competitors to Calendly and compare their pricing", type: "competitor_analysis" as AgentType },
];

export default function TasksPage() {
  const [goal, setGoal] = useState("");
  const [agentType, setAgentType] = useState<AgentType>("auto");
  const { run, loading, status } = useRunAgent();
  const recentTasks = useRecentTasks();
  const [detailId, setDetailId] = useState<string | null>(null);

  const handleRun = async (g?: string, t?: AgentType) => {
    const finalGoal = g ?? goal.trim();
    const finalType = t ?? agentType;
    if (!finalGoal) return;
    await run(finalGoal, finalType);
    if (!g) setGoal("");
  };

  return (
    <>
      <PageHeader title="Tasks" subtitle="Create, monitor, and inspect agent executions" />
      <PageContent>
        {/* New task form */}
        <Card className="mb-6">
          <CardHeader title="Create Task" />
          <div className="flex gap-2 mb-3">
            <input className="input flex-1" placeholder="Enter agent goal..."
              value={goal} onChange={(e) => setGoal(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) handleRun(); }} />
            <select className="input w-48"
              value={agentType} onChange={(e) => setAgentType(e.target.value as AgentType)}>
              {["auto", "lead_generation", "market_research", "competitor_analysis",
                "data_extraction", "outreach_drafting", "website_audit", "monitoring", "general"].map((v) => (
                <option key={v} value={v}>{v.replace(/_/g, " ")}</option>
              ))}
            </select>
            <button className="btn btn-primary" onClick={() => handleRun()} disabled={loading || !goal.trim()}>
              {loading ? <Spinner size={14} /> : <Icon d={ICONS.send.d} size={14} />}
              {loading ? status : "Run"}
            </button>
          </div>

          {/* Quick tasks */}
          <div className="section-label mb-2">Quick Tasks</div>
          <div className="grid grid-cols-2 gap-2">
            {QUICK_TASKS.map((qt) => (
              <button key={qt.goal} className="card-hover text-left p-2.5 cursor-pointer"
                onClick={() => handleRun(qt.goal, qt.type)}>
                <div className="flex items-center gap-1.5 mb-1">
                  <AgentTypeBadge type={qt.type} />
                </div>
                <p className="text-xs text-text2 leading-relaxed">{qt.goal}</p>
              </button>
            ))}
          </div>
        </Card>

        {/* Task list */}
        <Card>
          <CardHeader
            title="Task History"
            subtitle={`${recentTasks.length} recent tasks`}
            action={
              <span className="text-[11px] font-mono text-muted">click row for details</span>
            }
          />
          {recentTasks.length === 0 ? (
            <EmptyState icon="📋" title="No tasks yet" description="Create your first task above" />
          ) : (
            <div>
              {recentTasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-center gap-3 py-2.5 border-b border-border last:border-0 cursor-pointer hover:bg-surface2/40 -mx-4 px-4 rounded transition-colors"
                  onClick={() => setDetailId(task.id)}
                >
                  <StatusBadge status={task.status} />
                  <span className="flex-1 text-[13px] text-text truncate">{task.goal}</span>
                  <AgentTypeBadge type={task.agentType} />
                  <span className="text-[11px] font-mono text-muted hidden lg:block">
                    {new Date(task.createdAt).toLocaleString("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <span className="text-[10px] font-mono text-muted/40 hidden md:block">#{task.id.slice(0, 8)}</span>
                  <Icon d={ICONS.chevronRight.d} size={12} className="text-muted flex-shrink-0" />
                </div>
              ))}
            </div>
          )}
        </Card>

        {detailId && <TaskDetail taskId={detailId} onClose={() => setDetailId(null)} />}
      </PageContent>
    </>
  );
}
