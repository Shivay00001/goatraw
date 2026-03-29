"use client";
import { useState } from "react";
import { PageHeader, PageContent } from "@/components/layout/AppShell";
import { Card, CardHeader, Icon, ICONS, Spinner, CodeBlock } from "@/components/ui";
import { useWorkspace, useUsage } from "@/hooks";
import { useUser, useStore } from "@/store";
import { clsx } from "clsx";

const PLAN_FEATURES = {
  free: {
    color: "text-muted",
    border: "border-border",
    features: ["10 tasks/hour", "100 tasks/month", "50 memory facts", "2 cron jobs", "1 channel", "5 skills"],
    price: "₹0",
  },
  pro: {
    color: "text-accent2",
    border: "border-accent/30",
    features: ["100 tasks/hour", "2,000 tasks/month", "500 memory facts", "20 cron jobs", "5 channels", "50 skills", "Heartbeat daemon", "Priority support"],
    price: "₹2,999/mo",
  },
  enterprise: {
    color: "text-yellow",
    border: "border-yellow/30",
    features: ["1,000 tasks/hour", "Unlimited tasks", "Unlimited memory", "Unlimited cron", "All channels", "Unlimited skills", "API access", "White-label", "Dedicated support"],
    price: "₹14,999/mo",
  },
};

export default function SettingsPage() {
  const user = useUser();
  const logout = useStore((s) => s.logout);
  const { workspace, loading: wsLoading, rotateKey } = useWorkspace();
  const { current: usage, limits } = useUsage();
  const [rotating, setRotating] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);

  const handleRotate = async () => {
    setRotating(true);
    const key = await rotateKey();
    setNewApiKey(key);
    setRotating(false);
  };

  const currentPlan = user?.plan ?? "free";
  const planInfo = PLAN_FEATURES[currentPlan as keyof typeof PLAN_FEATURES];

  return (
    <>
      <PageHeader title="Settings" subtitle="Workspace, API keys, billing" />
      <PageContent>
        <div className="grid grid-cols-2 gap-6">
          {/* Workspace */}
          <Card className="col-span-2">
            <CardHeader title="Workspace" subtitle={`ID: ${workspace?.id ?? "—"}`} />
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-text2 block mb-1">Name</label>
                  <div className="input text-text">{workspace?.name ?? "—"}</div>
                </div>
                <div>
                  <label className="text-xs font-medium text-text2 block mb-1">Owner Email</label>
                  <div className="input text-text">{user?.email ?? "—"}</div>
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-text2">API Key</label>
                  <button className="text-[11px] text-muted hover:text-accent2 font-mono" onClick={() => setShowKey((s) => !s)}>
                    {showKey ? "hide" : "show"}
                  </button>
                </div>
                <div className="input font-mono text-[12px] text-accent2 mb-2 truncate">
                  {newApiKey
                    ? newApiKey
                    : showKey
                    ? workspace?.api_key ?? "—"
                    : `gr_${"•".repeat(24)}${workspace?.api_key?.slice(-6) ?? "••••••"}`}
                </div>
                <button className="btn btn-secondary text-xs w-full" onClick={handleRotate} disabled={rotating}>
                  {rotating ? <Spinner size={12} /> : <Icon d={ICONS.refresh.d} size={12} />}
                  {rotating ? "Rotating..." : "Rotate API Key"}
                </button>
                {newApiKey && (
                  <p className="text-[11px] text-yellow mt-2">
                    ⚠️ Copy this key now — it won't be shown again.
                  </p>
                )}
              </div>
            </div>
          </Card>

          {/* Usage */}
          <Card>
            <CardHeader title="Usage This Month" subtitle={usage?.period ?? ""} />
            <div className="space-y-4">
              {[
                { label: "Tasks Completed",  val: usage?.usage.tasks_completed ?? 0,   max: limits?.limits.tasks_per_month ?? 100,   unit: "tasks" },
                { label: "Steps Executed",   val: usage?.usage.steps_executed ?? 0,    max: -1,                                       unit: "steps" },
                { label: "Tokens Used",      val: usage?.usage.tokens_used ?? 0,       max: -1,                                       unit: "tokens" },
              ].map(({ label, val, max, unit }) => (
                <div key={label}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs text-text2">{label}</span>
                    <span className="text-xs font-mono text-accent2">
                      {val.toLocaleString()}{max > 0 ? ` / ${max.toLocaleString()}` : ""} {unit}
                    </span>
                  </div>
                  {max > 0 && (
                    <div className="w-full h-1.5 bg-surface2 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent rounded-full transition-all"
                        style={{ width: `${Math.min(100, (val / max) * 100)}%` }}
                      />
                    </div>
                  )}
                </div>
              ))}
              <div className="pt-2 border-t border-border">
                <div className="flex justify-between text-xs">
                  <span className="text-muted">Estimated Cost</span>
                  <span className="font-mono text-green">${usage?.usage.estimated_cost_usd?.toFixed(4) ?? "0.0000"}</span>
                </div>
              </div>
            </div>
          </Card>

          {/* Plan */}
          <Card>
            <CardHeader title="Current Plan" action={
              currentPlan !== "enterprise" && (
                <span className="badge">Upgrade Available</span>
              )
            } />
            <div className="space-y-3">
              {(Object.entries(PLAN_FEATURES) as [string, typeof PLAN_FEATURES.free][]).map(([plan, info]) => (
                <div key={plan}
                  className={clsx("p-3 rounded-xl border-2 transition-all", plan === currentPlan ? info.border + " bg-surface2" : "border-border opacity-50")}>
                  <div className="flex items-center justify-between mb-2">
                    <span className={clsx("font-mono font-bold uppercase text-sm", info.color)}>{plan}</span>
                    <span className={clsx("font-mono text-sm font-bold", info.color)}>{info.price}</span>
                  </div>
                  <ul className="space-y-0.5">
                    {info.features.slice(0, 4).map((f) => (
                      <li key={f} className="flex items-center gap-1.5 text-xs text-text2">
                        <Icon d={ICONS.check.d} size={10} className="text-green flex-shrink-0" />
                        {f}
                      </li>
                    ))}
                    {info.features.length > 4 && (
                      <li className="text-xs text-muted">+{info.features.length - 4} more</li>
                    )}
                  </ul>
                </div>
              ))}
            </div>
          </Card>

          {/* API Usage via Code */}
          <Card className="col-span-2">
            <CardHeader title="API Integration" subtitle="Use GoatRaw from any language" />
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="section-label mb-2">Python</div>
                <CodeBlock language="python" code={`import requests

API_KEY = "${workspace?.api_key?.slice(0, 12) ?? "gr_your_key"}..."
BASE    = "${process.env.NEXT_PUBLIC_API_URL ?? "https://goatraw-api.onrender.com"}"

# Create task
r = requests.post(f"{BASE}/task/create",
  headers={"Authorization": f"Bearer {API_KEY}"},
  json={"goal": "Find SaaS leads in Mumbai", "agent_type": "lead_generation"}
)
task_id = r.json()["task_id"]

# Poll for result
import time
while True:
  r = requests.get(f"{BASE}/task/{task_id}",
    headers={"Authorization": f"Bearer {API_KEY}"})
  data = r.json()
  if data["status"] in ("completed", "failed"):
    print(data["result"])
    break
  time.sleep(2)`} />
              </div>
              <div>
                <div className="section-label mb-2">JavaScript</div>
                <CodeBlock language="javascript" code={`const API_KEY = "${workspace?.api_key?.slice(0, 12) ?? "gr_your_key"}...";
const BASE    = "${process.env.NEXT_PUBLIC_API_URL ?? "https://goatraw-api.onrender.com"}";
const headers = { "Authorization": \`Bearer \${API_KEY}\` };

// Create task
const { task_id } = await fetch(\`\${BASE}/task/create\`, {
  method: "POST", headers,
  body: JSON.stringify({ goal: "Find SaaS leads", agent_type: "auto" })
}).then(r => r.json());

// Poll until done
let result;
while (!result) {
  const { status, result: r } = await fetch(
    \`\${BASE}/task/\${task_id}\`, { headers }
  ).then(r => r.json());
  if (status === "completed") result = r;
  else await new Promise(r => setTimeout(r, 2000));
}
console.log(result);`} />
              </div>
            </div>
          </Card>

          {/* Danger zone */}
          <Card className="col-span-2 border-red/20">
            <CardHeader title="Account" />
            <div className="flex items-center justify-between p-3 rounded-lg bg-red/5 border border-red/15">
              <div>
                <div className="text-sm font-semibold">Sign Out</div>
                <div className="text-xs text-muted">Clears your session. API key remains valid.</div>
              </div>
              <button className="btn btn-danger" onClick={logout}>
                <Icon d={ICONS.logout.d} size={13} /> Sign Out
              </button>
            </div>
          </Card>
        </div>
      </PageContent>
    </>
  );
}
