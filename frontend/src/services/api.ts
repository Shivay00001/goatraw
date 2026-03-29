/**
 * GoatRaw — API Service Layer
 * Centralised Axios client. All API calls go through here.
 */

import axios, { AxiosInstance, AxiosError } from "axios";
import type {
  AuthTokens, Task, TaskResult, CreateTaskRequest,
  Skill, MemoryFact, HeartbeatConfig, HeartbeatResult,
  CronJob, UsageStats, PlanLimits, Workspace,
  SessionEntry, AgentType,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Axios instance ────────────────────────────────────────────
const client: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

// ── Auth interceptor ──────────────────────────────────────────
client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      clearToken();
      if (typeof window !== "undefined") window.location.href = "/auth/login";
    }
    return Promise.reject(err);
  }
);

// ── Token helpers ─────────────────────────────────────────────
export const getToken  = () => (typeof window !== "undefined" ? localStorage.getItem("gr_token") ?? "" : "");
export const setToken  = (t: string) => localStorage.setItem("gr_token", t);
export const clearToken = () => localStorage.removeItem("gr_token");
export const isLoggedIn = () => !!getToken();

// ── Helper ────────────────────────────────────────────────────
const get  = <T>(url: string, params?: object) => client.get<T>(url, { params }).then(r => r.data);
const post = <T>(url: string, data?: unknown)  => client.post<T>(url, data).then(r => r.data);
const del  = <T>(url: string)                  => client.delete<T>(url).then(r => r.data);
const patch = <T>(url: string, data?: unknown) => client.patch<T>(url, data).then(r => r.data);

// ─────────────────────────────────────────────────────────────
// AUTH
// ─────────────────────────────────────────────────────────────
export const authApi = {
  register: (email: string, password: string, fullName: string) =>
    post<AuthTokens>("/users/register", { email, password, full_name: fullName }),

  login: (email: string, password: string) =>
    post<AuthTokens>("/users/login", { email, password }),

  me: () => get("/users/me"),
};

// ─────────────────────────────────────────────────────────────
// WORKSPACE
// ─────────────────────────────────────────────────────────────
export const workspaceApi = {
  get:          () => get<Workspace>("/workspace/me"),
  getApiKey:    () => get<{ api_key: string; workspace_id: string }>("/workspace/api-key"),
  rotateApiKey: () => post<{ api_key: string }>("/workspace/api-key/rotate"),
  updateSettings: (settings: Record<string, unknown>) => patch("/workspace/settings", settings),
};

// ─────────────────────────────────────────────────────────────
// TASKS
// ─────────────────────────────────────────────────────────────
export const tasksApi = {
  create: (body: CreateTaskRequest) =>
    post<{ task_id: string; status: string; poll_url: string }>("/task/create", body),

  get: (id: string) => get<{ task_id: string; status: string; result?: TaskResult }>(`/task/${id}`),

  cancel: (id: string) => del(`/task/${id}`),

  /** Poll until complete or failed (max 120 attempts × 2s = 4 min) */
  pollUntilDone: async (taskId: string, onStatusChange?: (s: string) => void): Promise<TaskResult | null> => {
    for (let i = 0; i < 120; i++) {
      const res = await tasksApi.get(taskId);
      onStatusChange?.(res.status);
      if (res.status === "completed" || res.status === "failed") {
        return res.result ?? null;
      }
      await new Promise(r => setTimeout(r, 2000));
    }
    return null;
  },
};

// ─────────────────────────────────────────────────────────────
// AGENTS
// ─────────────────────────────────────────────────────────────
export const agentsApi = {
  run: (goal: string, agentType: AgentType = "auto", context?: object) =>
    post<{ task_id: string; status: string; poll_url: string }>("/agent/run", {
      goal, agent_type: agentType, context, sync: false,
    }),

  leadGen: (niche: string, location: string, filters?: object) =>
    post<{ task_id: string }>("/agent/lead-gen", { niche, location, filters }),

  marketResearch: (topic: string) =>
    post<{ task_id: string }>("/agent/market-research", { topic }),

  competitorAnalysis: (company: string, industry: string) =>
    post<{ task_id: string }>("/agent/competitor-analysis", { company, industry }),
};

// ─────────────────────────────────────────────────────────────
// SKILLS
// ─────────────────────────────────────────────────────────────
export const skillsApi = {
  list: () => get<{ skills: Skill[]; total: number; builtin: number; custom: number }>("/skills/list"),

  get: (id: string) => get<Skill>(`/skills/${id}`),

  generate: (description: string) =>
    post<{ skill_id: string; name: string; status: string }>("/skills/generate", { description }),

  run: (skillId: string, inputs: object, asyncRun = true) =>
    post<{ task_id: string; skill_name: string; status: string } | TaskResult>(
      "/skills/run", { skill_id: skillId, inputs, async_run: asyncRun }
    ),

  delete: (id: string) => del(`/skills/${id}`),
};

// ─────────────────────────────────────────────────────────────
// MEMORY
// ─────────────────────────────────────────────────────────────
export const memoryApi = {
  getCoreMemory: () =>
    get<{ facts: MemoryFact[]; count: number; capacity: number }>("/memory/core"),

  upsertFact: (key: string, value: string, category: string) =>
    post("/memory/core", { key, value, category }),

  deleteFact: (key: string) => del(`/memory/core/${encodeURIComponent(key)}`),

  getSession: (sessionId?: string, lastN = 20) =>
    get<{ session_id: string; messages: SessionEntry[]; count: number }>(
      "/memory/session", { session_id: sessionId, last_n: lastN }
    ),

  clearSession: (sessionId: string) =>
    del(`/memory/session?session_id=${sessionId}`),

  search: (query: string, topK = 5) =>
    post<{ query: string; results: Array<{ content: string; category: string; similarity: number }>; count: number }>(
      "/memory/search", { query, top_k: topK }
    ),

  consolidate: () => post<{ status: string; message: string }>("/memory/consolidate"),

  getContext: (query = "") =>
    get<{ context: string; length: number }>("/memory/context", { query }),

  stats: () => get("/memory/stats"),
};

// ─────────────────────────────────────────────────────────────
// HEARTBEAT
// ─────────────────────────────────────────────────────────────
export const heartbeatApi = {
  getConfig: () => get<{ configured: boolean; config?: HeartbeatConfig }>("/heartbeat/config"),

  saveConfig: (cfg: Partial<HeartbeatConfig>) =>
    post<{ status: string }>("/heartbeat/config", cfg),

  trigger: () => post<{ status: string; result: HeartbeatResult }>("/heartbeat/trigger"),

  history: () =>
    get<{ history: Array<{ status: string; message: string; timestamp: string }>; count: number }>(
      "/heartbeat/history"
    ),

  disable: () => del("/heartbeat/config"),
};

// ─────────────────────────────────────────────────────────────
// CRON
// ─────────────────────────────────────────────────────────────
export const cronApi = {
  create: (data: {
    name: string; goal: string; agent_type?: AgentType;
    schedule_type?: string; interval_hours?: number;
    daily_time?: string; weekly_day?: number; skill_id?: string;
  }) => post<{ job_id: string; name: string; status: string; next_run: string }>("/cron/create", data),

  list: () => get<{ jobs: CronJob[]; total: number; active: number }>("/cron/list"),

  get: (id: string) => get<CronJob>(`/cron/${id}`),

  update: (id: string, data: Partial<CronJob>) => patch<CronJob>(`/cron/${id}`, data),

  delete: (id: string) => del(`/cron/${id}`),

  runNow: (id: string) =>
    post<{ job_id: string; status: string; message: string }>(`/cron/${id}/run`),
};

// ─────────────────────────────────────────────────────────────
// USAGE
// ─────────────────────────────────────────────────────────────
export const usageApi = {
  current:  () => get<UsageStats>("/usage/current"),
  history:  (months = 3) => get<{ history: UsageStats[] }>("/usage/history", { months }),
  limits:   () => get<PlanLimits>("/usage/limits"),
};

// ─────────────────────────────────────────────────────────────
// HEALTH
// ─────────────────────────────────────────────────────────────
export const healthApi = {
  ping:     () => get<{ status: string; service: string }>("/health/"),
  readiness:() => get<{ status: string; redis: string }>("/health/ready"),
};
