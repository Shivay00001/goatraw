-- ============================================================
-- GoatRaw - Complete SQL Schema
-- Run on Supabase SQL Editor or any PostgreSQL instance
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── USERS ────────────────────────────────────────────────────────────────────
CREATE TYPE plan_tier AS ENUM ('free', 'pro', 'enterprise');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    api_key         VARCHAR(64) UNIQUE,
    plan            plan_tier NOT NULL DEFAULT 'free',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    usage_count     INTEGER NOT NULL DEFAULT 0,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_api_key ON users(api_key);

-- ─── TASKS ────────────────────────────────────────────────────────────────────
CREATE TYPE task_status AS ENUM ('queued', 'planning', 'executing', 'completed', 'failed', 'cancelled');
CREATE TYPE task_type AS ENUM ('general', 'lead_generation', 'market_research', 'competitor_analysis', 'data_extraction');

CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal            TEXT NOT NULL,
    agent_type      task_type NOT NULL DEFAULT 'general',
    status          task_status NOT NULL DEFAULT 'queued',
    context         JSONB DEFAULT '{}',
    steps_taken     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);

-- ─── OUTPUTS ──────────────────────────────────────────────────────────────────
CREATE TABLE outputs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id     UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    summary     TEXT,
    data        JSONB DEFAULT '{}',
    trace       JSONB DEFAULT '{}',
    status      VARCHAR(50),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_outputs_task_id ON outputs(task_id);
CREATE INDEX idx_outputs_user_id ON outputs(user_id);

-- ─── AGENT LOGS ───────────────────────────────────────────────────────────────
CREATE TABLE agent_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id     UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    step_number INTEGER,
    log_type    VARCHAR(50),  -- plan | tool_call | tool_result | thought | output
    content     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_logs_task_id ON agent_logs(task_id);

-- ─── API USAGE TRACKING ───────────────────────────────────────────────────────
CREATE TABLE api_usage (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint    VARCHAR(255),
    method      VARCHAR(10),
    tokens_used INTEGER DEFAULT 0,
    cost_usd    NUMERIC(10, 6) DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_usage_user_id ON api_usage(user_id);
CREATE INDEX idx_api_usage_created_at ON api_usage(created_at DESC);

-- ─── Row Level Security (Supabase) ───────────────────────────────────────────
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE outputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own tasks"    ON tasks    FOR ALL USING (auth.uid()::uuid = user_id);
CREATE POLICY "Users see own outputs"  ON outputs  FOR ALL USING (auth.uid()::uuid = user_id);
CREATE POLICY "Users see own logs"     ON agent_logs FOR SELECT USING (
    task_id IN (SELECT id FROM tasks WHERE user_id = auth.uid()::uuid)
);
