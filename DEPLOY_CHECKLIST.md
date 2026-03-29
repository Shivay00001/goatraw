# GoatRaw v2 — Full Deployment Checklist

## Phase 1: Prerequisites (10 min)

### 1.1 Get Groq API Key (FREE — required)
```
1. Go to console.groq.com
2. Sign up → API Keys → Create Key
3. Copy key starting with gsk_
GROQ_API_KEY=gsk_your_key_here
```

### 1.2 Set up Supabase (FREE tier)
```
1. Go to supabase.com → New project
   - Name: goatraw
   - Password: use a strong password
   - Region: closest to your users (Southeast Asia for India/Gulf)

2. Wait ~2 min for provisioning

3. Go to: Settings → Database → Connection string
   - Choose: "Transaction mode" (port 6543)
   - Copy the URI
DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

4. Go to: SQL Editor → paste contents of database/schema.sql → Run
   ✓ Tables created

5. Go to: Settings → API
   SUPABASE_URL=https://[project-ref].supabase.co
   SUPABASE_KEY=[anon public key]
```

### 1.3 Set up Upstash Redis (FREE tier)
```
1. Go to upstash.com → Create database
   - Name: goatraw-redis
   - Type: Regional
   - Region: ap-southeast-1 (Singapore — closest for India/Gulf)

2. Copy Redis URL from dashboard
REDIS_URL=rediss://default:[password]@[host].upstash.io:6379
```

---

## Phase 2: Deploy Backend on Render (10 min)

### 2.1 Prepare repository
```bash
# Create GitHub repo
git init
git add .
git commit -m "GoatRaw v2 initial"
git remote add origin https://github.com/YOUR_USERNAME/goatraw.git
git push -u origin main
```

### 2.2 Deploy on Render
```
1. Go to render.com → Sign in
2. New → Blueprint
3. Connect GitHub → select goatraw repo
4. Render detects deploy/render.yaml automatically
5. Click "Apply"
6. Render creates 3 services:
   - goatraw-api    (Web Service, $7/mo)
   - goatraw-worker (Background Worker, $7/mo)
   - goatraw-redis  (Redis, free)
```

### 2.3 Set environment variables
```
In Render Dashboard → goatraw-api → Environment:

SECRET_KEY=<run: python3 -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=<from Supabase step 1.2>
REDIS_URL=<from Upstash step 1.3>
GROQ_API_KEY=<from step 1.1>
DEBUG=false
FRONTEND_URL=https://your-app.vercel.app

# Optional but recommended:
OPENAI_API_KEY=sk-...
SERPAPI_KEY=...

# Channels (add as you connect them):
TELEGRAM_BOT_TOKEN=...
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
SLACK_BOT_TOKEN=...
```

### 2.4 Verify deployment
```bash
# Health check
curl https://goatraw-api.onrender.com/health/
# Expected: {"status": "ok", "service": "GoatRaw API"}

# Readiness (Redis)
curl https://goatraw-api.onrender.com/health/ready
# Expected: {"status": "ready", "redis": "connected"}
```

---

## Phase 3: Deploy Frontend on Vercel (5 min)

```bash
cd frontend
npm install -g vercel

# Set API URL
echo "NEXT_PUBLIC_API_URL=https://goatraw-api.onrender.com" > .env.production

# Deploy
vercel --prod

# Follow prompts:
# - Link to existing project? N
# - Project name: goatraw
# - Directory: ./
```

**Or via Vercel Dashboard:**
```
1. vercel.com → New Project → Import Git Repository
2. Select your goatraw repo → frontend directory
3. Add env var:
   NEXT_PUBLIC_API_URL = https://goatraw-api.onrender.com
4. Deploy
```

---

## Phase 4: Connect Channels

### 4.1 Telegram Bot
```bash
# Step 1: Create bot
# Message @BotFather on Telegram → /newbot → follow prompts
# Copy bot token

# Step 2: Add to Render env vars
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHI...

# Step 3: Register webhook
WORKSPACE_ID="your_workspace_id"  # from GoatRaw settings page
BOT_TOKEN="your_bot_token"
API_URL="https://goatraw-api.onrender.com"

curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${API_URL}/webhook/telegram/${WORKSPACE_ID}"

# Expected: {"ok":true,"result":true}

# Step 4: Test
# Send /help to your bot
# Expected: GoatRaw help message
```

### 4.2 WhatsApp Business
```
1. meta.com/business → Business Suite → WhatsApp
   OR developers.facebook.com → Add product → WhatsApp

2. Set up a test phone number (free sandbox available)

3. Copy:
   WHATSAPP_ACCESS_TOKEN=...
   WHATSAPP_PHONE_NUMBER_ID=...
   
4. In Meta Developer Console → Webhooks:
   URL: https://goatraw-api.onrender.com/webhook/whatsapp/YOUR_WORKSPACE_ID
   Verify token: goatraw-verify
   Subscribe to: messages

5. Test: send a WhatsApp message to your test number
```

### 4.3 Slack
```
1. api.slack.com/apps → Create New App → From scratch
2. Features → Event Subscriptions → Enable
3. Request URL: https://goatraw-api.onrender.com/webhook/slack/YOUR_WORKSPACE_ID
4. Subscribe: message.channels, app_mention
5. OAuth & Permissions → Install to workspace
6. Copy Bot User OAuth Token
   SLACK_BOT_TOKEN=xoxb-...
7. Invite @goatraw to a channel
8. Test: @goatraw find me 10 leads in Mumbai
```

---

## Phase 5: Run Tests
```bash
cd backend
source .venv/bin/activate

# Unit tests (fast, no real services needed)
pytest tests/unit/ -v

# Integration tests (need PostgreSQL + Redis running)
pytest tests/integration/ -v

# Full suite with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Expected: 35+ tests passing
```

---

## Phase 6: First Task Test
```bash
# Register a user
curl -X POST https://goatraw-api.onrender.com/users/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@company.com","password":"password123","full_name":"Your Name"}'

# Copy access_token from response

# Create your first task
curl -X POST https://goatraw-api.onrender.com/task/create \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"goal":"Find 10 SaaS companies in Mumbai and extract their emails","agent_type":"lead_generation"}'

# Copy task_id, poll every 2 seconds:
curl https://goatraw-api.onrender.com/task/TASK_ID \
  -H "Authorization: Bearer YOUR_TOKEN"

# When status=completed, download CSV:
curl https://goatraw-api.onrender.com/export/TASK_ID/csv \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o leads.csv
```

---

## Monthly Costs (Render Free → Starter)

| Service | Plan | Cost |
|---------|------|------|
| goatraw-api | Render Starter | $7/mo |
| goatraw-worker | Render Starter | $7/mo |
| Redis | Upstash Free | $0 |
| Database | Supabase Free | $0 |
| Frontend | Vercel Free | $0 |
| **Total** | | **$14/mo** |

**Revenue potential:**
- 10 Pro users (₹2,999/mo) = ₹29,990/mo = ~$360/mo
- ROI from month 1: **25x**

---

## Troubleshooting

**Worker not processing tasks:**
```bash
# Check worker logs in Render Dashboard → goatraw-worker → Logs
# Common fix: verify REDIS_URL is set correctly
```

**Database connection failed:**
```bash
# Verify DATABASE_URL uses asyncpg driver:
# postgresql+asyncpg://... NOT postgresql://...
```

**LLM calls timing out:**
```bash
# Groq is most reliable for free tier
# Ensure GROQ_API_KEY is set
# Check Groq console.groq.com for rate limits
```

**Telegram webhook not receiving messages:**
```bash
# Verify webhook is registered:
curl "https://api.telegram.org/bot{TOKEN}/getWebhookInfo"

# If not set, re-run setWebhook command from Phase 4.1
```
