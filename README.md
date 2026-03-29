# 🦅 GoatRaw v2 — Autonomous AI Agent SaaS

> OpenClaw, rebuilt for the cloud. Every capability. Multi-tenant. Deployable in 10 minutes.

---

## Complete OpenClaw → GoatRaw Feature Map

| OpenClaw Feature | GoatRaw Implementation | File |
|---|---|---|
| 3-tier memory (Markdown files) | Redis Core + rolling Session + pgvector Deep | `agents/memory_system.py` |
| SKILL.md + ClawHub registry | SkillHub: 5 built-in + AI-generated custom | `agents/skill_system.py` |
| Heartbeat daemon | Per-user heartbeat, silent-OK, Telegram/webhook | `workers/heartbeat.py` |
| Cron / recurring actions | Scheduler: interval/daily/weekly | `workers/scheduler.py` |
| 50+ channel inbox | Telegram · WhatsApp · Slack · Discord · Webhook | `api/routes/channels.py` |
| Slash commands | /status, /help, /run, /skills, /memory | `api/routes/channels.py` |
| CDP browser control | Playwright async browser tool | `agents/browser_tool.py` |
| Multi-agent delegation | SubAgentDelegator — LLM routing | `agents/orchestrator_v2.py` |
| Smart monitoring | SmartMonitor MD5 diff, notify on change only | `agents/orchestrator_v2.py` |
| Nightly memory consolidation | LLM extraction to deep memory | `agents/memory_system.py` |
| Self-improving skill generation | `generate_skill()` from description | `agents/skill_system.py` |
| Plan → replan on failure | `replan_task()` mid-execution recovery | `agents/orchestrator_v2.py` |
| Multi-LLM support | Groq → OpenAI → Together fallback chain | `services/llm_adapter.py` |
| Email finder | Apollo + Hunter + pattern guessing | `utils/email_finder.py` |
| LinkedIn research | SERP-based + RapidAPI enrichment | `utils/linkedin_scraper.py` |
| Rate limiting | Redis sliding window per plan tier | `core/redis_client.py` |
| Multi-tenant workspaces | Workspace API + API key rotation | `api/routes/workspace.py` |
| CSV/Sheets export | Full export service | `utils/export.py` |
| Outbound notifications | Telegram/WhatsApp/Slack/Webhook | `services/notification_service.py` |
| Lead Gen use-case | LeadGenAgent — complete end-to-end | `agents/lead_gen_agent.py` |

## 🚀 Deploy in 10 Minutes

### Render (recommended)
```
1. Fork repo → render.com → New → Blueprint → deploy/render.yaml
2. Set: GROQ_API_KEY, DATABASE_URL (Supabase), REDIS_URL (Upstash)
3. Click Apply
4. cd frontend && npx vercel --prod
```

### Local Dev
```bash
chmod +x setup.sh && ./setup.sh
# Terminal 1: cd backend && uvicorn main:app --reload
# Terminal 2: python -m app.worker_v2
# Terminal 3: cd frontend && npm run dev
```

## Required Env Vars

| Var | Source |
|-----|--------|
| SECRET_KEY | openssl rand -hex 32 |
| DATABASE_URL | Supabase connection string |
| REDIS_URL | upstash.com |
| GROQ_API_KEY | console.groq.com (FREE) |

Optional: OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, SERPAPI_KEY, APOLLO_API_KEY, HUNTER_API_KEY

## Monetisation

| Plan | Tasks/Hr | Price |
|------|----------|-------|
| Free | 10 | ₹0 |
| Pro | 100 | ₹2,999/mo |
| Enterprise | 1,000 | ₹14,999/mo |

## Make Commands
```bash
make dev-api       # Start API
make dev-worker    # Start worker
make test          # Run tests
make migrate       # Apply DB migrations
make docker-up     # Full stack
```
