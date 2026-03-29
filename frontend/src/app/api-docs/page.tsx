"use client";
import { useState } from "react";
import { PageHeader, PageContent } from "@/components/layout/AppShell";
import { Card, CardHeader, CodeBlock, Icon, ICONS } from "@/components/ui";
import { useWorkspace } from "@/hooks";
import { clsx } from "clsx";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "https://goatraw-api.onrender.com";

interface Endpoint {
  method:      "GET" | "POST" | "DELETE" | "PATCH";
  path:        string;
  description: string;
  body?:       object;
  response?:   object;
  auth:        boolean;
}

const ENDPOINTS: { section: string; endpoints: Endpoint[] }[] = [
  {
    section: "Tasks",
    endpoints: [
      {
        method: "POST", path: "/task/create", auth: true,
        description: "Create and queue an agent task",
        body:     { goal: "Find 20 SaaS companies in Bangalore", agent_type: "lead_generation" },
        response: { task_id: "abc-123", status: "queued", poll_url: "/task/abc-123" },
      },
      {
        method: "GET", path: "/task/{id}", auth: true,
        description: "Poll task status and retrieve result",
        response: { task_id: "abc-123", status: "completed", result: { output: { data: "..." } } },
      },
      {
        method: "DELETE", path: "/task/{id}", auth: true,
        description: "Cancel a queued task",
        response: { task_id: "abc-123", status: "cancelled" },
      },
    ],
  },
  {
    section: "Agents",
    endpoints: [
      {
        method: "POST", path: "/agent/lead-gen", auth: true,
        description: "Run lead generation agent",
        body:     { niche: "real estate agencies", location: "Dubai", filters: {} },
        response: { task_id: "xyz", niche: "real estate agencies", poll_url: "/task/xyz" },
      },
      {
        method: "POST", path: "/agent/market-research", auth: true,
        description: "Run market research agent",
        body:     { topic: "AI CRM software" },
        response: { task_id: "xyz", poll_url: "/task/xyz" },
      },
      {
        method: "POST", path: "/agent/competitor-analysis", auth: true,
        description: "Run competitor analysis agent",
        body:     { company: "our_product", industry: "SaaS" },
        response: { task_id: "xyz", poll_url: "/task/xyz" },
      },
    ],
  },
  {
    section: "Skills",
    endpoints: [
      {
        method: "GET", path: "/skills/list", auth: true,
        description: "List all workspace skills",
        response: { skills: [], total: 5, builtin: 5, custom: 0 },
      },
      {
        method: "POST", path: "/skills/generate", auth: true,
        description: "AI-generate a new skill from description",
        body:     { description: "Scrape G2 reviews and extract top complaints" },
        response: { skill_id: "abc", name: "G2 Review Scraper", status: "generated_and_installed" },
      },
      {
        method: "POST", path: "/skills/run", auth: true,
        description: "Execute a skill with inputs",
        body:     { skill_id: "lead_scraper", inputs: { niche: "SaaS", location: "Mumbai" } },
        response: { task_id: "xyz", skill_name: "Lead Scraper", status: "queued" },
      },
    ],
  },
  {
    section: "Memory",
    endpoints: [
      {
        method: "GET",  path: "/memory/core", auth: true,
        description: "Get all Tier 1 core memory facts",
        response: { facts: [], count: 0, capacity: 50 },
      },
      {
        method: "POST", path: "/memory/core", auth: true,
        description: "Add or update a core memory fact",
        body:     { key: "target_market", value: "Mumbai B2B SaaS", category: "project" },
        response: { status: "saved", key: "target_market" },
      },
      {
        method: "POST", path: "/memory/search", auth: true,
        description: "Semantic search across deep memory",
        body:     { query: "Dubai leads", top_k: 5 },
        response: { results: [], count: 0 },
      },
      {
        method: "POST", path: "/memory/consolidate", auth: true,
        description: "Trigger nightly memory consolidation",
        response: { status: "consolidated_5_memories", message: "Memory consolidation complete." },
      },
    ],
  },
  {
    section: "Heartbeat & Cron",
    endpoints: [
      {
        method: "POST", path: "/heartbeat/config", auth: true,
        description: "Configure the proactive heartbeat daemon",
        body: {
          enabled: true, interval_minutes: 30,
          checklist: ["Check lead replies"],
          notify_channel: "telegram", notify_endpoint: "-1001234567",
        },
        response: { status: "saved", enabled: true },
      },
      {
        method: "POST", path: "/cron/create", auth: true,
        description: "Create a scheduled recurring workflow",
        body: {
          name: "Daily Lead Hunt", goal: "Find 10 new SaaS leads in Mumbai",
          schedule_type: "daily", daily_time: "08:00",
        },
        response: { job_id: "abc123", status: "scheduled", next_run: "2026-03-28T08:00:00Z" },
      },
    ],
  },
  {
    section: "Export",
    endpoints: [
      {
        method: "GET", path: "/export/{task_id}/csv", auth: true,
        description: "Download task output as CSV file",
        response: { note: "Returns CSV file download" },
      },
      {
        method: "GET", path: "/export/{task_id}/json", auth: true,
        description: "Download full task result as JSON",
        response: { note: "Returns JSON file download" },
      },
    ],
  },
];

const METHOD_COLORS: Record<string, string> = {
  GET:    "bg-blue/10 text-blue border-blue/30",
  POST:   "bg-green/10 text-green border-green/30",
  DELETE: "bg-red/10 text-red border-red/30",
  PATCH:  "bg-yellow/10 text-yellow border-yellow/30",
};

function EndpointRow({ ep, apiBase, apiKey }: { ep: Endpoint; apiBase: string; apiKey: string }) {
  const [expanded, setExpanded] = useState(false);

  const curlExample = [
    `curl -X ${ep.method} \\`,
    `  ${apiBase}${ep.path.replace("{id}", "abc-123").replace("{task_id}", "abc-123")} \\`,
    `  -H "Authorization: Bearer ${apiKey ? apiKey.slice(0, 12) + "..." : "YOUR_API_KEY"}" \\`,
    ep.body ? `  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify(ep.body, null, 2)}'` : "",
  ].filter(Boolean).join("\n");

  return (
    <div className="border border-border rounded-xl overflow-hidden mb-3">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface2 transition-colors text-left"
        onClick={() => setExpanded((e) => !e)}
      >
        <span className={clsx("text-[11px] font-mono font-bold px-2 py-0.5 rounded border min-w-[50px] text-center", METHOD_COLORS[ep.method])}>
          {ep.method}
        </span>
        <code className="text-[13px] font-mono text-accent2 flex-1">{ep.path}</code>
        <span className="text-xs text-muted">{ep.description}</span>
        {ep.auth && <span className="badge text-[9px]">auth</span>}
        <Icon d={ICONS.chevronDown.d} size={12} className={clsx("text-muted transition-transform flex-shrink-0", expanded && "rotate-180")} />
      </button>

      {expanded && (
        <div className="border-t border-border p-4 bg-surface2/40 space-y-4">
          {ep.body && (
            <div>
              <div className="section-label mb-2">Request Body</div>
              <CodeBlock code={JSON.stringify(ep.body, null, 2)} language="json" />
            </div>
          )}
          {ep.response && (
            <div>
              <div className="section-label mb-2">Example Response</div>
              <CodeBlock code={JSON.stringify(ep.response, null, 2)} language="json" />
            </div>
          )}
          <div>
            <div className="section-label mb-2">cURL</div>
            <CodeBlock code={curlExample} language="bash" />
          </div>
        </div>
      )}
    </div>
  );
}

export default function ApiDocsPage() {
  const { workspace } = useWorkspace();
  const apiKey = workspace?.api_key ?? "";
  const [search, setSearch] = useState("");

  const filtered = ENDPOINTS.map((section) => ({
    ...section,
    endpoints: section.endpoints.filter((ep) =>
      !search ||
      ep.path.toLowerCase().includes(search.toLowerCase()) ||
      ep.description.toLowerCase().includes(search.toLowerCase())
    ),
  })).filter((s) => s.endpoints.length > 0);

  return (
    <>
      <PageHeader
        title="API Reference"
        subtitle={`Base URL: ${API_BASE}`}
        action={<a href={`${API_BASE}/docs`} target="_blank" rel="noopener noreferrer" className="btn btn-secondary text-xs"><Icon d={ICONS.link.d} size={12} /> Swagger UI</a>}
      />
      <PageContent>
        {/* Auth info */}
        <Card className="mb-6 border-accent/20">
          <div className="flex items-start gap-3">
            <Icon d={ICONS.key.d} size={16} className="text-accent2 mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-sm font-semibold mb-1">Authentication</div>
              <p className="text-xs text-muted mb-2">All endpoints require a Bearer token. Get your API key from the Settings page.</p>
              <code className="text-xs font-mono text-accent2 bg-surface2 px-2 py-1 rounded border border-border">
                Authorization: Bearer {apiKey ? apiKey.slice(0, 12) + "..." : "gr_your_api_key"}
              </code>
            </div>
          </div>
        </Card>

        {/* Search */}
        <input className="input mb-6" placeholder="Search endpoints..." value={search} onChange={(e) => setSearch(e.target.value)} />

        {/* Endpoints */}
        {filtered.map((section) => (
          <div key={section.section} className="mb-6">
            <div className="section-label mb-3">{section.section}</div>
            {section.endpoints.map((ep) => (
              <EndpointRow key={ep.path + ep.method} ep={ep} apiBase={API_BASE} apiKey={apiKey} />
            ))}
          </div>
        ))}

        {/* Python SDK snippet */}
        <Card className="mt-6">
          <CardHeader title="Python SDK Quick Start" subtitle="pip install requests" />
          <CodeBlock language="python" code={`import requests, time

BASE    = "${API_BASE}"
API_KEY = "${apiKey ? apiKey.slice(0, 12) + "..." : "gr_your_key"}"
headers = {"Authorization": f"Bearer {API_KEY}"}

def run_agent(goal, agent_type="auto"):
    """Run any GoatRaw agent and wait for result."""
    # Create task
    r = requests.post(f"{BASE}/task/create",
        headers=headers,
        json={"goal": goal, "agent_type": agent_type})
    task_id = r.json()["task_id"]
    print(f"Task created: {task_id}")

    # Poll until done
    while True:
        r = requests.get(f"{BASE}/task/{task_id}", headers=headers)
        data = r.json()
        print(f"Status: {data['status']}")
        if data["status"] in ("completed", "failed"):
            return data["result"]
        time.sleep(2)

# Example usage
result = run_agent("Find 10 SaaS companies in Mumbai", "lead_generation")
leads  = result["output"]["data"]
print(f"Found {len(leads)} leads!")
for lead in leads[:3]:
    print(f"  {lead['company_name']} - {lead.get('email', 'no email')}")`}
          />
        </Card>
      </PageContent>
    </>
  );
}
