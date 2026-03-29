# GoatRaw v2 — Makefile
# Usage: make <target>

.PHONY: setup dev-api dev-worker dev-frontend test lint migrate docker-up docker-down clean

# ── Setup ─────────────────────────────────────────────────────
setup:
	chmod +x setup.sh && ./setup.sh

# ── Development ───────────────────────────────────────────────
dev-api:
	cd backend && source .venv/bin/activate && \
	uvicorn main:app --reload --port 8000

dev-worker:
	cd backend && source .venv/bin/activate && \
	python -m app.worker_v2

dev-frontend:
	cd frontend && npm run dev

# ── Tests ─────────────────────────────────────────────────────
test:
	cd backend && source .venv/bin/activate && \
	pytest tests/ -v --tb=short

test-unit:
	cd backend && source .venv/bin/activate && \
	pytest tests/unit/ -v

test-integration:
	cd backend && source .venv/bin/activate && \
	pytest tests/integration/ -v

test-cov:
	cd backend && source .venv/bin/activate && \
	pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# ── Database ──────────────────────────────────────────────────
migrate:
	cd backend && source .venv/bin/activate && alembic upgrade head

migrate-new:
	cd backend && source .venv/bin/activate && \
	alembic revision --autogenerate -m "$(MSG)"

migrate-rollback:
	cd backend && source .venv/bin/activate && alembic downgrade -1

# ── Docker ───────────────────────────────────────────────────
docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api worker

docker-build:
	docker compose build

# ── Lint ─────────────────────────────────────────────────────
lint:
	cd backend && source .venv/bin/activate && \
	python -m py_compile $$(find app -name "*.py") && echo "✓ No syntax errors"

# ── Clean ────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .venv -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".DS_Store" -delete 2>/dev/null || true
	echo "✓ Cleaned"
