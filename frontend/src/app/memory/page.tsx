"use client";
import { useState } from "react";
import { PageHeader, PageContent } from "@/components/layout/AppShell";
import { Card, CardHeader, Icon, ICONS, Spinner, Input, EmptyState, Modal } from "@/components/ui";
import { useMemory } from "@/hooks";
import { clsx } from "clsx";
import type { MemoryCategory } from "@/types";

const CATEGORY_STYLES: Record<string, string> = {
  preference: "text-accent2 bg-accent/10 border-accent/20",
  identity:   "text-blue border-blue/20 bg-blue/10",
  project:    "text-green bg-green/10 border-green/20",
  knowledge:  "text-muted bg-surface2 border-border",
  contact:    "text-orange bg-orange/10 border-orange/20",
  decision:   "text-yellow bg-yellow/10 border-yellow/20",
};

const CATEGORIES: MemoryCategory[] = ["preference", "identity", "project", "knowledge", "contact", "decision"];

export default function MemoryPage() {
  const { facts, count, capacity, loading, upsert, remove, consolidate } = useMemory();
  const [newKey, setNewKey] = useState("");
  const [newVal, setNewVal] = useState("");
  const [newCat, setNewCat] = useState<MemoryCategory>("knowledge");
  const [adding, setAdding] = useState(false);
  const [consolidating, setConsolidating] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const handleAdd = async () => {
    if (!newKey.trim() || !newVal.trim()) return;
    setAdding(true);
    await upsert(newKey.trim(), newVal.trim(), newCat);
    setNewKey(""); setNewVal("");
    setAdding(false);
  };

  const handleConsolidate = async () => {
    setConsolidating(true);
    await consolidate();
    setConsolidating(false);
  };

  const filtered = facts.filter((f) =>
    !searchQuery || f.key.toLowerCase().includes(searchQuery.toLowerCase()) || f.value.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      <PageHeader
        title="Memory System"
        subtitle="3-tier persistent context across all tasks"
        action={
          <button className="btn btn-secondary" onClick={handleConsolidate} disabled={consolidating}>
            {consolidating ? <Spinner size={13} /> : <Icon d={ICONS.refresh.d} size={13} />}
            Consolidate
          </button>
        }
      />
      <PageContent>
        <div className="grid grid-cols-2 gap-6 mb-6">
          {/* Tier 1 */}
          <Card className="col-span-2">
            <CardHeader
              title="Tier 1 — Core Memory"
              subtitle={`Always loaded in every agent context · ${count} / ${capacity} facts`}
              action={<span className="badge badge-green">ACTIVE</span>}
            />

            {/* Search */}
            <input className="input mb-4" placeholder="Search facts..." value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)} />

            {/* Facts list */}
            <div className="space-y-0 divide-y divide-border">
              {loading ? (
                [...Array(4)].map((_, i) => (
                  <div key={i} className="flex gap-3 py-2.5 animate-pulse">
                    <div className="h-3 bg-surface2 rounded w-28" />
                    <div className="h-3 bg-surface2 rounded flex-1" />
                    <div className="h-3 bg-surface2 rounded w-16" />
                  </div>
                ))
              ) : filtered.length === 0 ? (
                <EmptyState icon="🧠" title="No facts yet" description="Add your first memory fact below" />
              ) : (
                filtered.map((fact, i) => (
                  <div key={i} className="flex items-center gap-3 py-2.5 group">
                    <span className="font-mono text-[11px] text-accent2 min-w-[140px] truncate">{fact.key}</span>
                    <span className="flex-1 text-sm text-text">{fact.value}</span>
                    <span className={clsx("text-[10px] font-mono px-1.5 py-0.5 rounded border", CATEGORY_STYLES[fact.category] ?? CATEGORY_STYLES.knowledge)}>
                      {fact.category}
                    </span>
                    <button
                      onClick={() => remove(fact.key)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 text-muted hover:text-red transition-all"
                    >
                      <Icon d={ICONS.x.d} size={12} />
                    </button>
                  </div>
                ))
              )}
            </div>

            {/* Add fact */}
            <div className="flex items-end gap-2 mt-4 pt-4 border-t border-border">
              <div className="flex-1">
                <Input label="Key" placeholder="e.g. target_market" value={newKey} onChange={(e) => setNewKey(e.target.value)} />
              </div>
              <div className="flex-[2]">
                <Input label="Value" placeholder="e.g. Mumbai SaaS companies" value={newVal} onChange={(e) => setNewVal(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") handleAdd(); }} />
              </div>
              <div>
                <label className="text-xs font-medium text-text2 block mb-1.5">Category</label>
                <select className="input py-2" value={newCat} onChange={(e) => setNewCat(e.target.value as MemoryCategory)}>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <button className="btn btn-primary" onClick={handleAdd} disabled={adding || !newKey || !newVal}>
                {adding ? <Spinner size={13} /> : <Icon d={ICONS.plus.d} size={13} />}
              </button>
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Tier 2 */}
          <Card>
            <CardHeader title="Tier 2 — Session Memory" subtitle="Rolling 48h context window" action={<span className="badge">LIVE</span>} />
            <div className="space-y-0 divide-y divide-border text-sm">
              {[
                { role: "user",  content: "Find real estate agencies in Dubai",         t: "14:22" },
                { role: "agent", content: "Found 18 agencies, extracted 14 emails",     t: "14:24" },
                { role: "user",  content: "Draft outreach emails for the top 5",        t: "14:25" },
                { role: "agent", content: "Drafted 5 personalized emails",              t: "14:27" },
              ].map((e, i) => (
                <div key={i} className="flex gap-2 py-2.5">
                  <span className={clsx("font-mono text-[10px] min-w-[38px] pt-0.5", e.role === "user" ? "text-accent2" : "text-green")}>
                    {e.role}
                  </span>
                  <span className="flex-1 text-[12.5px]">{e.content}</span>
                  <span className="font-mono text-[10px] text-muted">{e.t}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Tier 3 */}
          <Card>
            <CardHeader title="Tier 3 — Deep Memory" subtitle="Long-term semantic knowledge store" />
            <div className="grid grid-cols-2 gap-4 mb-4">
              {[
                { label: "People",    count: 23, color: "text-accent2" },
                { label: "Projects",  count: 8,  color: "text-green" },
                { label: "Topics",    count: 45, color: "text-yellow" },
                { label: "Decisions", count: 12, color: "text-orange" },
              ].map((c) => (
                <div key={c.label} className="bg-surface2 rounded-lg p-3 text-center">
                  <div className={clsx("text-xl font-bold font-mono", c.color)}>{c.count}</div>
                  <div className="text-[11px] text-muted mt-0.5">{c.label}</div>
                </div>
              ))}
            </div>
            <button className="btn btn-secondary w-full text-xs" onClick={handleConsolidate} disabled={consolidating}>
              {consolidating ? <Spinner size={13} /> : <Icon d={ICONS.refresh.d} size={13} />}
              Run Nightly Consolidation Now
            </button>
            <p className="text-[11px] text-muted mt-2 text-center">
              Auto-runs nightly. Extracts durable facts from session history.
            </p>
          </Card>
        </div>
      </PageContent>
    </>
  );
}
