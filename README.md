<div align="center">
  <img src="https://via.placeholder.com/1000x250/1e293b/ffffff?text=GoatRaw+v2+%E2%80%94+Autonomous+AI+Agent+SaaS" alt="GoatRaw Banner">

  <h1>🦅 GoatRaw v2</h1>
  <p><strong>OpenClaw rebuilt for the cloud. Every capability. Multi-tenant. Deployable in 10 minutes.</strong></p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python Version">
    <img src="https://img.shields.io/badge/Next.js-14-black.svg" alt="Next.js">
    <img src="https://img.shields.io/badge/FastAPI-0.100+-green.svg" alt="FastAPI">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
    <img src="https://img.shields.io/badge/Status-Active-success.svg" alt="Status">
  </p>
</div>

---

## 📖 Table of Contents
- [Overview](#-overview)
- [Feature Map](#-feature-map)
- [Quick Start](#-deploy-in-10-minutes)
- [Architecture](#-architecture)
- [Monetization](#-monetisation)
- [Development](#-development)

---

## 🌟 Overview

GoatRaw v2 is a scalable, cloud-first implementation of the OpenClaw autonomous AI agent framework. It provides a robust, multi-tenant environment designed to handle everything from recurring cron jobs to complex web scraping and outreach tasks, all orchestrated by robust LLM agents.

## 🛠 Feature Map

Here is how the original OpenClaw features map to the current **GoatRaw** implementation:

| OpenClaw Feature | GoatRaw Implementation | File |
|---|---|---|
| **3-tier memory** (Markdown files) | Redis Core + rolling Session + pgvector Deep | `agents/memory_system.py` |
| **SKILL.md + ClawHub registry** | SkillHub: 5 built-in + AI-generated custom | `agents/skill_system.py` |
| **Heartbeat daemon** | Per-user heartbeat, silent-OK, Telegram/webhook | `workers/heartbeat.py` |
| **Cron / recurring actions** | Scheduler: interval/daily/weekly | `workers/scheduler.py` |
| **50+ channel inbox** | Telegram · WhatsApp · Slack · Discord · Webhook | `api/routes/channels.py` |
| **Slash commands** | `/status`, `/help`, `/run`, `/skills`, `/memory` | `api/routes/channels.py` |
| **CDP browser control** | Playwright async browser tool | `agents/browser_tool.py` |
| **Multi-agent delegation** | SubAgentDelegator — LLM routing | `agents/orchestrator_v2.py` |
| **Smart monitoring** | SmartMonitor MD5 diff, notify on change only | `agents/orchestrator_v2.py` |
| **Nightly memory consolidation** | LLM extraction to deep memory | `agents/memory_system.py` |
| **Self-improving skill generation**| `generate_skill()` from description | `agents/skill_system.py` |
| **Plan → replan on failure** | `replan_task()` mid-execution recovery | `agents/orchestrator_v2.py` |
| **Multi-LLM support** | Groq → OpenAI → Together fallback chain | `services/llm_adapter.py` |
| **Email finder** | Apollo + Hunter + pattern guessing | `utils/email_finder.py` |
| **LinkedIn research** | SERP-based + RapidAPI enrichment | `utils/linkedin_scraper.py` |
| **Rate limiting** | Redis sliding window per plan tier | `core/redis_client.py` |
| **Multi-tenant workspaces** | Workspace API + API key rotation | `api/routes/workspace.py` |
| **CSV/Sheets export** | Full export service | `utils/export.py` |
| **Outbound notifications** | Telegram / WhatsApp / Slack / Webhook | `services/notification_service.py` |
| **Lead Gen use-case** | LeadGenAgent — complete end-to-end | `agents/lead_gen_agent.py` |

---

## 🚀 Deploy in 10 Minutes

### Render (Recommended)

1. Fork this repository and head over to [Render](https://render.com/).
2. Create a **New Blueprint** and select the `deploy/render.yaml` file from your repo.
3. Set the following environment variables:
   - `GROQ_API_KEY`
   - `DATABASE_URL` *(Supabase)*
   - `REDIS_URL` *(Upstash)*
4. Click **Apply**.
5. *For Frontend:* Navigate to `cd frontend` and run `npx vercel --prod`.

### Local Development

Get up and running locally quickly via the provided setup script:

```bash
chmod +x setup.sh && ./setup.sh
```

Run the components in separate terminals:

```bash
# Terminal 1 (Backend API):
cd backend && uvicorn main:app --reload

# Terminal 2 (Worker Node):
cd backend && python -m app.worker_v2

# Terminal 3 (Frontend App):
cd frontend && npm run dev
```

---

## ⚙️ Configuration & Environment

| Variable | Description / Source |
|---|---|
| `SECRET_KEY` | Run `openssl rand -hex 32` |
| `DATABASE_URL` | Your Supabase Postgres connection string |
| `REDIS_URL` | Your Upstash Redis connection string |
| `GROQ_API_KEY` | Available for free at [console.groq.com](https://console.groq.com) |

> **Optional Enhancements:** `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `SERPAPI_KEY`, `APOLLO_API_KEY`, `HUNTER_API_KEY`

---

## 💎 Monetisation

The default configuration includes tiered access mapping perfectly to SaaS implementations:

| Plan | Tasks/Hr | Monthly Price |
|------|----------|---------------|
| **Free** | 10 | ₹0 |
| **Pro** | 100 | ₹2,999/mo |
| **Enterprise** | 1,000+ | ₹14,999/mo |

---

## 🛠 Development Commands

A comprehensive `Makefile` handles standard operations:

```bash
make dev-api       # Start API server
make dev-worker    # Start worker process
make test          # Run test suite
make migrate       # Apply database migrations
make docker-up     # Spin up the full local stack via Docker Compose
```

<div align="center">
  <br/>
  <p>Built with ❤️ by the GoatRaw Team.</p>
</div>
