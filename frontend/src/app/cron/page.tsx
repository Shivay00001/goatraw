"use client";
import { useState } from "react";
import { PageHeader, PageContent } from "@/components/layout/AppShell";
import {
  Card, CardHeader, Icon, ICONS, Spinner, Modal,
  Input, EmptyState, Toggle, SkeletonRow,
} from "@/components/ui";
import { useCron } from "@/hooks";
import { clsx } from "clsx";
import type { CronJob, AgentType, ScheduleType } from "@/types";

const SCHEDULE_LABELS: Record<ScheduleType, string> = {
  interval: "Every N hours",
  daily:    "Daily at time",
  weekly:   "Weekly on day",
};

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function CronJobRow({ job, onToggle, onDelete, onRunNow }: {
  job: CronJob;
  onToggle: (id: string, enabled: boolean) => void;
  onDelete: (id: string) => void;
  onRunNow: (id: string) => void;
}) {
  const scheduleDesc =
    job.schedule_type === "interval" ? `Every ${job.interval_hours}h`
    : job.schedule_type === "daily"  ? `Daily ${job.daily_time} UTC`
    : `${DAY_NAMES[job.weekly_day]} ${job.daily_time} UTC`;

  return (
    <div className="flex items-center gap-4 py-3 border-b border-border last:border-0 group">
      <div className={clsx("w-1.5 h-1.5 rounded-full flex-shrink-0", job.enabled ? "bg-green" : "bg-muted")} />
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-semibold truncate">{job.name}</div>
        <div className="text-[11px] text-muted truncate mt-0.5">{job.goal}</div>
      </div>
      <div className="hidden md:block text-right">
        <div className="text-[11px] font-mono text-accent2">{scheduleDesc}</div>
        <div className="text-[10px] text-muted mt-0.5">
          {job.last_run ? `last: ${new Date(job.last_run).toLocaleString("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}` : "never run"}
        </div>
      </div>
      <div className="text-[10px] font-mono text-muted hidden lg:block">×{job.run_count}</div>
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button className="btn btn-ghost p-1.5 text-xs" onClick={() => onRunNow(job.id)} title="Run now">
          <Icon d={ICONS.send.d} size={12} />
        </button>
        <Toggle checked={job.enabled} onChange={(v) => onToggle(job.id, v)} />
        <button className="btn btn-ghost p-1.5 text-red/70 hover:text-red" onClick={() => onDelete(job.id)} title="Delete">
          <Icon d={ICONS.trash.d} size={12} />
        </button>
      </div>
    </div>
  );
}

const BLANK_FORM = {
  name: "", goal: "", agent_type: "auto" as AgentType,
  schedule_type: "daily" as ScheduleType,
  interval_hours: 24, daily_time: "08:00", weekly_day: 0,
};

export default function CronPage() {
  const { jobs, total, active, loading, create, toggle, remove, runNow } = useCron();
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ ...BLANK_FORM });
  const [creating, setCreating] = useState(false);

  const f = (key: keyof typeof BLANK_FORM, val: unknown) =>
    setForm((prev) => ({ ...prev, [key]: val }));

  const handleCreate = async () => {
    if (!form.name.trim() || !form.goal.trim()) return;
    setCreating(true);
    await create(form);
    setForm({ ...BLANK_FORM });
    setShowModal(false);
    setCreating(false);
  };

  return (
    <>
      <PageHeader
        title="Scheduled Workflows"
        subtitle={`${active} active · ${total} total — OpenClaw recurring tasks`}
        action={
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            <Icon d={ICONS.plus.d} size={14} /> New Schedule
          </button>
        }
      />
      <PageContent>
        {/* Summary cards */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[
            { label: "Active Jobs",    value: active,           icon: "🟢" },
            { label: "Total Runs",     value: jobs.reduce((s, j) => s + j.run_count, 0), icon: "⚡" },
            { label: "Next Run",       value: jobs.filter(j => j.enabled).length > 0 ? "< 1h" : "None", icon: "⏰" },
          ].map((s) => (
            <div key={s.label} className="card flex items-center gap-3">
              <span className="text-2xl">{s.icon}</span>
              <div>
                <div className="text-xl font-bold font-mono text-accent2">{s.value}</div>
                <div className="text-xs text-muted">{s.label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Jobs list */}
        <Card>
          <CardHeader title="Scheduled Jobs" subtitle="Runs automatically on your set schedule" />
          {loading ? (
            <div>{[...Array(3)].map((_, i) => <SkeletonRow key={i} />)}</div>
          ) : jobs.length === 0 ? (
            <EmptyState
              icon="⏰"
              title="No schedules yet"
              description="Create a recurring workflow to automate repetitive tasks"
              action={
                <button className="btn btn-primary mt-2" onClick={() => setShowModal(true)}>
                  <Icon d={ICONS.plus.d} size={14} /> Create First Schedule
                </button>
              }
            />
          ) : (
            jobs.map((job) => (
              <CronJobRow
                key={job.id} job={job}
                onToggle={toggle}
                onDelete={remove}
                onRunNow={runNow}
              />
            ))
          )}
        </Card>

        {/* Example ideas */}
        <Card className="mt-6">
          <CardHeader title="Schedule Ideas" subtitle="Click to pre-fill the form" />
          <div className="grid grid-cols-2 gap-3">
            {[
              { name: "Daily Lead Hunt",       goal: "Find 10 new SaaS companies in Mumbai and extract contact details",             schedule: "Daily 8:00 AM" },
              { name: "Competitor Pulse",      goal: "Check competitor pricing and feature updates",                                  schedule: "Every 12h" },
              { name: "Weekly Market Brief",   goal: "Summarize AI industry funding news this week and list top 5 deals",            schedule: "Monday 9 AM" },
              { name: "Lead Follow-up Check",  goal: "Check if any leads from last week replied and summarize their responses",       schedule: "Daily 6 PM" },
            ].map((idea) => (
              <button
                key={idea.name}
                className="card-hover text-left p-3 cursor-pointer"
                onClick={() => { setForm((f) => ({ ...f, name: idea.name, goal: idea.goal })); setShowModal(true); }}
              >
                <div className="text-[12.5px] font-semibold mb-1">{idea.name}</div>
                <div className="text-[11px] text-muted truncate">{idea.goal}</div>
                <div className="text-[10px] font-mono text-accent2 mt-1">{idea.schedule}</div>
              </button>
            ))}
          </div>
        </Card>

        {/* Create modal */}
        <Modal open={showModal} onClose={() => setShowModal(false)} title="New Scheduled Workflow">
          <div className="space-y-4">
            <Input label="Name" placeholder="Daily Lead Hunt" value={form.name} onChange={(e) => f("name", e.target.value)} />
            <div>
              <label className="text-xs font-medium text-text2 block mb-1.5">Goal</label>
              <textarea className="input resize-none" rows={3}
                placeholder="Describe what the agent should do each time..."
                value={form.goal} onChange={(e) => f("goal", e.target.value)} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-text2 block mb-1.5">Schedule Type</label>
                <select className="input" value={form.schedule_type} onChange={(e) => f("schedule_type", e.target.value)}>
                  {(Object.entries(SCHEDULE_LABELS) as [ScheduleType, string][]).map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-text2 block mb-1.5">Agent Type</label>
                <select className="input" value={form.agent_type} onChange={(e) => f("agent_type", e.target.value)}>
                  {["auto", "lead_generation", "market_research", "competitor_analysis", "monitoring", "general"].map((v) => (
                    <option key={v} value={v}>{v.replace(/_/g, " ")}</option>
                  ))}
                </select>
              </div>
            </div>

            {form.schedule_type === "interval" && (
              <Input label="Every N hours" type="number" min={1} max={168}
                value={form.interval_hours} onChange={(e) => f("interval_hours", +e.target.value)} />
            )}
            {(form.schedule_type === "daily" || form.schedule_type === "weekly") && (
              <Input label="Time (UTC)" type="time" value={form.daily_time} onChange={(e) => f("daily_time", e.target.value)} />
            )}
            {form.schedule_type === "weekly" && (
              <div>
                <label className="text-xs font-medium text-text2 block mb-1.5">Day of Week</label>
                <div className="flex gap-1.5">
                  {DAY_NAMES.map((d, i) => (
                    <button key={d} onClick={() => f("weekly_day", i)}
                      className={clsx("flex-1 py-1.5 rounded text-[11px] font-mono border transition-colors",
                        form.weekly_day === i ? "bg-accent/20 text-accent2 border-accent/40" : "bg-surface2 text-muted border-border hover:border-border2")}>
                      {d}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <button className="btn btn-secondary flex-1" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary flex-1" onClick={handleCreate} disabled={creating || !form.name || !form.goal}>
                {creating ? <Spinner size={14} /> : <Icon d={ICONS.check.d} size={14} />}
                {creating ? "Creating..." : "Create Schedule"}
              </button>
            </div>
          </div>
        </Modal>
      </PageContent>
    </>
  );
}
