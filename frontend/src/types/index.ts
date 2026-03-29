// GoatRaw — shared TypeScript types

export type PlanTier = "free" | "pro" | "enterprise";
export type TaskStatus = "queued" | "planning" | "executing" | "completed" | "failed" | "cancelled";
export type AgentType =
  | "auto"
  | "general"
  | "lead_generation"
  | "market_research"
  | "competitor_analysis"
  | "data_extraction"
  | "outreach_drafting"
  | "website_audit"
  | "monitoring";
export type ScheduleType = "interval" | "daily" | "weekly";
export type NotifyChannel = "webhook" | "telegram" | "slack" | "email";

// ── Auth ──────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  full_name: string;
  plan: PlanTier;
  workspace_id: string;
  api_key?: string;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
  user_id: string;
  plan: PlanTier;
  api_key: string;
}

// ── Tasks ─────────────────────────────────────────────────────
export interface Task {
  id: string;
  goal: string;
  agent_type: AgentType;
  status: TaskStatus;
  steps_taken: number;
  context?: Record<string, unknown>;
  skill_id?: string;
  cron_job_id?: string;
  source: string;
  created_at: string;
  completed_at?: string;
}

export interface TaskOutput {
  summary: string;
  status: "success" | "partial" | "failed";
  data: unknown;
  stats?: Record<string, number>;
  next_steps?: string[];
}

export interface TaskResult {
  task_id: string;
  goal: string;
  agent_type: AgentType;
  status: TaskStatus;
  output?: TaskOutput;
  error?: string;
  steps_taken: number;
  completed_at: string;
  trace?: unknown;
}

export interface CreateTaskRequest {
  goal: string;
  agent_type?: AgentType;
  context?: Record<string, unknown>;
  priority?: "normal" | "high";
}

// ── Skills ────────────────────────────────────────────────────
export interface SkillStep {
  tool: string;
  params_template: Record<string, unknown>;
  description?: string;
}

export interface Skill {
  id: string;
  name: string;
  description: string;
  category: string;
  steps: SkillStep[];
  input_schema: Record<string, string>;
  output_schema: Record<string, string>;
  author: string;
  version: string;
  tags: string[];
  created_at: string;
}

// ── Memory ────────────────────────────────────────────────────
export type MemoryCategory = "preference" | "identity" | "project" | "knowledge" | "contact" | "decision";

export interface MemoryFact {
  key: string;
  value: string;
  category: MemoryCategory;
  confidence: number;
  created_at: string;
  last_accessed: string;
}

export interface SessionEntry {
  session_id: string;
  role: "user" | "agent" | "tool";
  content: string;
  metadata?: Record<string, unknown>;
  timestamp: string;
}

// ── Heartbeat ─────────────────────────────────────────────────
export interface HeartbeatConfig {
  user_id: string;
  enabled: boolean;
  interval_minutes: number;
  checklist: string[];
  notify_channel: NotifyChannel;
  notify_endpoint: string;
  silent_ok: boolean;
  last_run?: string;
  next_run?: string;
}

export interface HeartbeatResult {
  status: "OK" | "ACTION_NEEDED" | "error";
  message: string;
  actions_taken?: string[];
  recommended_actions?: string[];
}

// ── Cron ──────────────────────────────────────────────────────
export interface CronJob {
  id: string;
  user_id: string;
  name: string;
  goal: string;
  agent_type: AgentType;
  schedule_type: ScheduleType;
  interval_hours: number;
  daily_time: string;
  weekly_day: number;
  enabled: boolean;
  last_run?: string;
  run_count: number;
  created_at: string;
}

// ── Channels ──────────────────────────────────────────────────
export type ChannelType = "telegram" | "whatsapp" | "slack" | "discord" | "webhook";

export interface Channel {
  type: ChannelType;
  name: string;
  connected: boolean;
  endpoint?: string;
  description?: string;
}

// ── Usage ─────────────────────────────────────────────────────
export interface UsageStats {
  period: string;
  plan: PlanTier;
  usage: {
    tasks_completed: number;
    steps_executed: number;
    tokens_used: number;
    estimated_cost_usd: number;
  };
}

export interface PlanLimits {
  plan: PlanTier;
  limits: {
    tasks_per_hour: number;
    tasks_per_month: number;
    memory_facts: number;
    cron_jobs: number;
    channels: number;
    skills: number;
    price_inr: number;
    price_usd: number;
  };
  current: {
    tasks_this_hour: number;
    tasks_this_month: number;
  };
}

// ── Workspace ─────────────────────────────────────────────────
export interface Workspace {
  id: string;
  owner_id: string;
  name: string;
  description: string;
  api_key: string;
  members: Array<{ user_id: string; role: "admin" | "member" }>;
  settings: Record<string, unknown>;
  created_at: string;
}

// ── API response wrappers ─────────────────────────────────────
export interface ApiError {
  error: string;
  detail?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}
