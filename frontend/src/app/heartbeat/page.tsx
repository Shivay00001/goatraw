"use client";
import { useState, useEffect } from "react";
import { PageHeader, PageContent } from "@/components/layout/AppShell";
import { Card, CardHeader, Icon, ICONS, Spinner, Toggle } from "@/components/ui";
import { useHeartbeat } from "@/hooks";

export default function HeartbeatPage() {
  const { config, configured, history, loading, save, trigger } = useHeartbeat();
  const [enabled, setEnabled]         = useState(true);
  const [interval, setInterval]       = useState(30);
  const [notifyCh, setNotifyCh]       = useState("webhook");
  const [notifyEp, setNotifyEp]       = useState("");
  const [silentOk, setSilentOk]       = useState(true);
  const [checklist, setChecklist]     = useState<string[]>([
    "Check if any leads responded to outreach",
    "Monitor competitor pricing changes",
    "Review pending task queue",
  ]);
  const [newItem, setNewItem]         = useState("");
  const [saving, setSaving]           = useState(false);
  const [triggering, setTriggering]   = useState(false);

  useEffect(() => {
    if (config) {
      setEnabled(config.enabled);
      setInterval(config.interval_minutes);
      setNotifyCh(config.notify_channel);
      setNotifyEp(config.notify_endpoint);
      setSilentOk(config.silent_ok);
      setChecklist(config.checklist);
    }
  }, [config]);

  const handleSave = async () => {
    setSaving(true);
    await save({ enabled, interval_minutes: interval, notify_channel: notifyCh, notify_endpoint: notifyEp, silent_ok: silentOk, checklist });
    setSaving(false);
  };

  const handleTrigger = async () => {
    setTriggering(true);
    await trigger();
    setTriggering(false);
  };

  return (
    <>
      <PageHeader
        title="Heartbeat"
        subtitle="Proactive monitoring — wakes up on schedule and acts"
        action={
          <div className="flex gap-2">
            <button className="btn btn-secondary" onClick={handleTrigger} disabled={triggering}>
              {triggering ? <Spinner size={13} /> : <Icon d={ICONS.zap.d} size={13} />}
              Fire Now
            </button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? <Spinner size={13} /> : <Icon d={ICONS.check.d} size={13} />}
              Save Config
            </button>
          </div>
        }
      />
      <PageContent>
        <div className="grid grid-cols-2 gap-6 mb-6">
          {/* Config */}
          <Card>
            <CardHeader title="Configuration" subtitle="OpenClaw heartbeat daemon adapted for SaaS" />
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">Enable Heartbeat</div>
                  <div className="text-xs text-muted">Agent wakes up on schedule</div>
                </div>
                <Toggle checked={enabled} onChange={setEnabled} />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">Interval</label>
                  <span className="font-mono text-xs text-accent2">{interval} min</span>
                </div>
                <input type="range" min={5} max={120} step={5} value={interval}
                  onChange={(e) => setInterval(+e.target.value)}
                  className="w-full accent-accent cursor-pointer" />
                <div className="flex justify-between text-[10px] text-muted mt-1">
                  <span>5 min</span><span>30 min</span><span>1 hour</span><span>2 hours</span>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-text2 block mb-1.5">Notification Channel</label>
                <select className="input" value={notifyCh} onChange={(e) => setNotifyCh(e.target.value)}>
                  <option value="webhook">🔗 Webhook</option>
                  <option value="telegram">🤖 Telegram</option>
                  <option value="slack">🟦 Slack</option>
                  <option value="email">📧 Email</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-text2 block mb-1.5">
                  {notifyCh === "telegram" ? "Telegram Chat ID" : notifyCh === "slack" ? "Slack Channel ID" : "Webhook URL"}
                </label>
                <input className="input" placeholder={notifyCh === "webhook" ? "https://..." : "-1001234567890"}
                  value={notifyEp} onChange={(e) => setNotifyEp(e.target.value)} />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">Silent OK Mode</div>
                  <div className="text-xs text-muted">Only notify when action needed</div>
                </div>
                <Toggle checked={silentOk} onChange={setSilentOk} />
              </div>
            </div>
          </Card>

          {/* Checklist */}
          <Card>
            <CardHeader title="Checklist" subtitle="Items checked every heartbeat" />
            <div className="space-y-0 divide-y divide-border mb-4">
              {checklist.map((item, i) => (
                <div key={i} className="flex items-center gap-2 py-2.5 group">
                  <span className="w-1.5 h-1.5 rounded-full bg-green flex-shrink-0" />
                  <span className="flex-1 text-sm">{item}</span>
                  <button onClick={() => setChecklist((c) => c.filter((_, j) => j !== i))}
                    className="opacity-0 group-hover:opacity-100 text-muted hover:text-red p-0.5 transition-all">
                    <Icon d={ICONS.x.d} size={11} />
                  </button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <input className="input flex-1 text-xs" placeholder="Add checklist item..."
                value={newItem} onChange={(e) => setNewItem(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && newItem.trim()) { setChecklist((c) => [...c, newItem.trim()]); setNewItem(""); } }} />
              <button className="btn btn-primary btn-sm" onClick={() => { if (newItem.trim()) { setChecklist((c) => [...c, newItem.trim()]); setNewItem(""); } }}>
                <Icon d={ICONS.plus.d} size={13} />
              </button>
            </div>
          </Card>
        </div>

        {/* Beat History */}
        <Card>
          <CardHeader title="Recent Heartbeats" subtitle="Last 20 beat results" />
          {history.length === 0 ? (
            <div className="py-8 text-center text-muted text-sm">No heartbeat history yet. Click "Fire Now" to test.</div>
          ) : (
            <div className="divide-y divide-border">
              {history.map((h: { status: string; message: string; timestamp?: string }, i) => (
                <div key={i} className="flex items-center gap-3 py-2.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${h.status === "OK" ? "bg-green" : "bg-yellow"}`} />
                  <span className="font-mono text-[10px] text-muted min-w-[60px]">{h.status}</span>
                  <span className="flex-1 text-sm text-text">{h.message}</span>
                  {h.timestamp && <span className="font-mono text-[10px] text-muted">{new Date(h.timestamp).toLocaleTimeString()}</span>}
                </div>
              ))}
            </div>
          )}
        </Card>
      </PageContent>
    </>
  );
}
