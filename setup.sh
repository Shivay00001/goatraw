#!/bin/bash
# GoatRaw v2 — Local Setup Script
# Run: chmod +x setup.sh && ./setup.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════╗"
echo "  ║        GoatRaw v2 Setup           ║"
echo "  ║   Autonomous AI Agent Platform    ║"
echo "  ╚═══════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Check prerequisites ────────────────────────────────────
echo -e "${YELLOW}Checking prerequisites...${NC}"
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 required. Install it first."; exit 1; }
command -v node >/dev/null 2>&1    || { echo "❌ node required. Install it first."; exit 1; }
command -v docker >/dev/null 2>&1  || { echo "⚠️  Docker not found (optional for local dev)"; }

# ── 2. Backend setup ──────────────────────────────────────────
echo -e "\n${YELLOW}Setting up backend...${NC}"
cd backend

# Create virtual env
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -q -r requirements.txt
pip install -q -r requirements-test.txt

# Create .env from example
if [ ! -f .env ]; then
  cp .env.example .env
  # Generate SECRET_KEY
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i "s/change-me-in-production/$SECRET/g" .env
  echo -e "${GREEN}✓ .env created with random SECRET_KEY${NC}"
  echo -e "${YELLOW}⚠️  Edit backend/.env and add your API keys!${NC}"
fi

cd ..

# ── 3. Frontend setup ─────────────────────────────────────────
echo -e "\n${YELLOW}Setting up frontend...${NC}"
cd frontend

npm install --silent

if [ ! -f .env.local ]; then
  echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
  echo -e "${GREEN}✓ frontend/.env.local created${NC}"
fi

cd ..

# ── 4. Docker Compose (local full stack) ─────────────────────
echo -e "\n${YELLOW}Starting local services (Docker)...${NC}"
if command -v docker >/dev/null 2>&1; then
  docker compose up postgres redis -d
  echo -e "${GREEN}✓ PostgreSQL + Redis started${NC}"
  sleep 3

  # Run migrations
  cd backend
  source .venv/bin/activate
  alembic upgrade head
  echo -e "${GREEN}✓ Database migrations applied${NC}"
  cd ..
else
  echo "⚠️  Skipping Docker (not installed). Start PostgreSQL and Redis manually."
fi

# ── 5. Print next steps ───────────────────────────────────────
echo -e "\n${CYAN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✓ GoatRaw setup complete!${NC}"
echo -e "${CYAN}═══════════════════════════════════════${NC}"
echo ""
echo "NEXT STEPS:"
echo ""
echo "  1. Edit backend/.env and add your API keys:"
echo "     GROQ_API_KEY=gsk_...    (free at console.groq.com)"
echo "     OPENAI_API_KEY=sk-...   (optional)"
echo ""
echo "  2. Start the API server:"
echo "     cd backend && source .venv/bin/activate"
echo "     uvicorn main:app --reload --port 8000"
echo ""
echo "  3. Start the background worker (new terminal):"
echo "     cd backend && source .venv/bin/activate"
echo "     python -m app.worker_v2"
echo ""
echo "  4. Start the frontend (new terminal):"
echo "     cd frontend && npm run dev"
echo ""
echo "  5. Open http://localhost:3000"
echo ""
echo "  API Docs: http://localhost:8000/docs (DEBUG=true only)"
echo ""
echo -e "${YELLOW}For Render deployment: see deploy/render.yaml${NC}"
