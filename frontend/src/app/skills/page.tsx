"use client";
import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader, PageContent } from "@/components/layout/AppShell";
import { Card, CardHeader, Icon, ICONS, Spinner, Modal, Input, EmptyState, SkeletonCard } from "@/components/ui";
import { useSkills } from "@/hooks";
import { clsx } from "clsx";
import type { Skill } from "@/types";

const CATEGORY_COLORS: Record<string, string> = {
  lead_gen:   "bg-accent/10 text-accent2 border-accent/20",
  research:   "bg-blue/10 text-blue border-blue/20",
  outreach:   "bg-green/10 text-green border-green/20",
  monitoring: "bg-yellow/10 text-yellow border-yellow/20",
  custom:     "bg-orange/10 text-orange border-orange/20",
};

function SkillCard({ skill, onRun, onDelete }: { skill: Skill; onRun: (s: Skill) => void; onDelete: (id: string) => void }) {
  const catCls = CATEGORY_COLORS[skill.category] ?? CATEGORY_COLORS.custom;
  return (
    <div className="card-hover group cursor-pointer" onClick={() => onRun(skill)}>
      <div className="flex items-start justify-between mb-2.5">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-accent" />
            <span className="text-[13.5px] font-semibold">{skill.name}</span>
          </div>
          <span className={clsx("text-[10px] font-mono px-1.5 py-0.5 rounded border mt-1 inline-block", catCls)}>
            {skill.category}
          </span>
        </div>
        {skill.author !== "system" && (
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(skill.id); }}
            className="opacity-0 group-hover:opacity-100 btn-ghost p-1 rounded text-red/70 hover:text-red transition-all"
          >
            <Icon d={ICONS.trash.d} size={12} />
          </button>
        )}
      </div>
      <p className="text-xs text-muted mb-3 leading-relaxed">{skill.description}</p>
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-1">
          {skill.tags.slice(0, 3).map((t) => (
            <span key={t} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface2 text-muted border border-border">
              {t}
            </span>
          ))}
        </div>
        <span className="text-[10px] font-mono text-muted">{skill.steps.length} steps</span>
      </div>
    </div>
  );
}

export default function SkillsPage() {
  const { skills, loading, builtin, custom, generate, runSkill, deleteSkill } = useSkills();
  const [genDesc, setGenDesc] = useState("");
  const [generating, setGenerating] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [running, setRunning] = useState(false);

  const handleGenerate = async () => {
    if (!genDesc.trim()) return;
    setGenerating(true);
    await generate(genDesc.trim());
    setGenDesc("");
    setGenerating(false);
  };

  const handleRunSkill = async () => {
    if (!selectedSkill) return;
    setRunning(true);
    await runSkill(selectedSkill.id, inputs);
    setRunning(false);
    setSelectedSkill(null);
    setInputs({});
  };

  return (
    <>
      <PageHeader
        title="Skill Hub"
        subtitle={`${builtin} built-in · ${custom} custom`}
        action={
          <span className="text-[11px] font-mono text-muted">
            OpenClaw SKILL.md → GoatRaw SkillHub
          </span>
        }
      />
      <PageContent>
        {/* Generate new skill */}
        <Card className="mb-6">
          <CardHeader title="Generate Skill with AI" subtitle="Describe what you need — GoatRaw writes the skill for you" />
          <div className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="e.g. 'Scrape G2 reviews and extract top 5 pain points as JSON'"
              value={genDesc}
              onChange={(e) => setGenDesc(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleGenerate(); }}
            />
            <button className="btn btn-primary" onClick={handleGenerate} disabled={generating || !genDesc.trim()}>
              {generating ? <Spinner size={14} /> : <Icon d={ICONS.zap.d} size={14} />}
              {generating ? "Generating..." : "Generate"}
            </button>
          </div>
          <p className="text-[11px] text-muted mt-2">
            AI will write a multi-step skill using your available tools and auto-install it to your workspace.
          </p>
        </Card>

        {/* Skills grid */}
        {loading ? (
          <div className="grid grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => <SkeletonCard key={i} />)}
          </div>
        ) : skills.length === 0 ? (
          <EmptyState icon="🧩" title="No skills yet" description="Generate your first skill above" />
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {skills.map((s) => (
              <SkillCard key={s.id} skill={s} onRun={setSelectedSkill} onDelete={deleteSkill} />
            ))}
          </div>
        )}

        {/* Run skill modal */}
        <Modal open={!!selectedSkill} onClose={() => setSelectedSkill(null)} title={`Run: ${selectedSkill?.name}`}>
          {selectedSkill && (
            <div className="space-y-4">
              <p className="text-sm text-muted">{selectedSkill.description}</p>
              <div className="space-y-3">
                {Object.entries(selectedSkill.input_schema).map(([key, type]) => (
                  <Input
                    key={key}
                    label={`${key} (${type})`}
                    placeholder={`Enter ${key}...`}
                    value={inputs[key] ?? ""}
                    onChange={(e) => setInputs((prev) => ({ ...prev, [key]: e.target.value }))}
                  />
                ))}
              </div>
              <button className="btn btn-primary w-full" onClick={handleRunSkill} disabled={running}>
                {running ? <Spinner size={14} /> : <Icon d={ICONS.send.d} size={14} />}
                {running ? "Running..." : "Run Skill"}
              </button>
            </div>
          )}
        </Modal>
      </PageContent>
    </>
  );
}
