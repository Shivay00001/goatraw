/**
 * GoatRaw — Custom React Hooks
 * SWR-based data fetching + mutation helpers.
 */

import useSWR, { mutate } from "swr";
import { useCallback, useState } from "react";
import {
  tasksApi, agentsApi, skillsApi, memoryApi,
  heartbeatApi, cronApi, usageApi, workspaceApi,
} from "@/services/api";
import { useStore, useNotify } from "@/store";
import type { AgentType, CreateTaskRequest, MemoryCategory } from "@/types";

// ── SWR Fetcher ───────────────────────────────────────────────
const fetcher = (fn: () => Promise<unknown>) => fn();

// ─────────────────────────────────────────────────────────────
// useRunAgent — creates a task, polls, updates store
// ─────────────────────────────────────────────────────────────
export function useRunAgent() {
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const { addTask, updateTaskStatus } = useStore();
  const notify = useNotify();

  const run = useCallback(async (goal: string, agentType: AgentType = "auto", context?: object) => {
    setLoading(true);
    setStatus("queued");
    try {
      const res = await agentsApi.run(goal, agentType, context);
      const id = res.task_id;
      setTaskId(id);
      addTask({ id, goal, status: "queued", agentType, createdAt: new Date().toISOString() });

      // Poll
      const result = await tasksApi.pollUntilDone(id, (s) => {
        setStatus(s);
        updateTaskStatus(id, s as never);
      });

      if (result) {
        updateTaskStatus(id, result.status, result);
        if (result.status === "completed") notify("success", "Task completed!");
        else notify("error", `Task failed: ${result.error ?? "unknown"}`);
      }
      return result;
    } catch (e: unknown) {
      notify("error", (e as Error).message ?? "Task failed");
      return null;
    } finally {
      setLoading(false);
    }
  }, [addTask, updateTaskStatus, notify]);

  return { run, loading, taskId, status };
}

// ─────────────────────────────────────────────────────────────
// useTasks — recent task list
// ─────────────────────────────────────────────────────────────
export function useTaskStatus(taskId: string | null) {
  const { data, error } = useSWR(
    taskId ? `task-${taskId}` : null,
    () => tasksApi.get(taskId!),
    { refreshInterval: (data) => (data?.status === "completed" || data?.status === "failed" ? 0 : 2000) }
  );
  return { data, loading: !data && !error, error };
}

// ─────────────────────────────────────────────────────────────
// useSkills
// ─────────────────────────────────────────────────────────────
export function useSkills() {
  const { data, error, isLoading } = useSWR("skills", () => skillsApi.list());
  const notify = useNotify();

  const generate = useCallback(async (description: string) => {
    try {
      const result = await skillsApi.generate(description);
      mutate("skills");
      notify("success", `Skill "${result.name}" generated!`);
      return result;
    } catch {
      notify("error", "Skill generation failed.");
      return null;
    }
  }, [notify]);

  const runSkill = useCallback(async (skillId: string, inputs: object) => {
    try {
      return await skillsApi.run(skillId, inputs, true);
    } catch (e) {
      notify("error", "Failed to run skill.");
      return null;
    }
  }, [notify]);

  const deleteSkill = useCallback(async (id: string) => {
    await skillsApi.delete(id);
    mutate("skills");
    notify("success", "Skill deleted.");
  }, [notify]);

  return {
    skills: data?.skills ?? [],
    total: data?.total ?? 0,
    builtin: data?.builtin ?? 0,
    custom: data?.custom ?? 0,
    loading: isLoading,
    error,
    generate,
    runSkill,
    deleteSkill,
  };
}

// ─────────────────────────────────────────────────────────────
// useMemory
// ─────────────────────────────────────────────────────────────
export function useMemory() {
  const { data, error, isLoading } = useSWR("memory-core", () => memoryApi.getCoreMemory());
  const notify = useNotify();

  const upsert = useCallback(async (key: string, value: string, category: MemoryCategory) => {
    await memoryApi.upsertFact(key, value, category);
    mutate("memory-core");
    notify("success", "Memory saved.");
  }, [notify]);

  const remove = useCallback(async (key: string) => {
    await memoryApi.deleteFact(key);
    mutate("memory-core");
    notify("success", "Memory removed.");
  }, [notify]);

  const consolidate = useCallback(async () => {
    const res = await memoryApi.consolidate();
    mutate("memory-core");
    notify("success", res.message);
    return res;
  }, [notify]);

  return {
    facts: data?.facts ?? [],
    count: data?.count ?? 0,
    capacity: data?.capacity ?? 50,
    loading: isLoading,
    error,
    upsert,
    remove,
    consolidate,
  };
}

// ─────────────────────────────────────────────────────────────
// useHeartbeat
// ─────────────────────────────────────────────────────────────
export function useHeartbeat() {
  const { data, error, isLoading } = useSWR("heartbeat-config", () => heartbeatApi.getConfig());
  const { data: history } = useSWR("heartbeat-history", () => heartbeatApi.history());
  const notify = useNotify();

  const save = useCallback(async (cfg: object) => {
    await heartbeatApi.saveConfig(cfg);
    mutate("heartbeat-config");
    notify("success", "Heartbeat config saved.");
  }, [notify]);

  const trigger = useCallback(async () => {
    const res = await heartbeatApi.trigger();
    mutate("heartbeat-history");
    notify("info", `Heartbeat fired: ${res.result.status}`);
    return res;
  }, [notify]);

  return {
    config: data?.config,
    configured: data?.configured ?? false,
    history: history?.history ?? [],
    loading: isLoading,
    save,
    trigger,
  };
}

// ─────────────────────────────────────────────────────────────
// useCron
// ─────────────────────────────────────────────────────────────
export function useCron() {
  const { data, error, isLoading } = useSWR("cron-jobs", () => cronApi.list());
  const notify = useNotify();

  const create = useCallback(async (jobData: object) => {
    const res = await cronApi.create(jobData as never);
    mutate("cron-jobs");
    notify("success", `"${(jobData as {name: string}).name}" scheduled.`);
    return res;
  }, [notify]);

  const toggle = useCallback(async (id: string, enabled: boolean) => {
    await cronApi.update(id, { enabled });
    mutate("cron-jobs");
  }, []);

  const remove = useCallback(async (id: string) => {
    await cronApi.delete(id);
    mutate("cron-jobs");
    notify("success", "Cron job deleted.");
  }, [notify]);

  const runNow = useCallback(async (id: string) => {
    const res = await cronApi.runNow(id);
    notify("info", "Job triggered. Check tasks for result.");
    return res;
  }, [notify]);

  return {
    jobs: data?.jobs ?? [],
    total: data?.total ?? 0,
    active: data?.active ?? 0,
    loading: isLoading,
    create, toggle, remove, runNow,
  };
}

// ─────────────────────────────────────────────────────────────
// useUsage
// ─────────────────────────────────────────────────────────────
export function useUsage() {
  const { data: current } = useSWR("usage-current", () => usageApi.current());
  const { data: limits  } = useSWR("usage-limits",  () => usageApi.limits());
  return { current, limits };
}

// ─────────────────────────────────────────────────────────────
// useWorkspace
// ─────────────────────────────────────────────────────────────
export function useWorkspace() {
  const { data, isLoading } = useSWR("workspace", () => workspaceApi.get());
  const notify = useNotify();

  const rotateKey = useCallback(async () => {
    const res = await workspaceApi.rotateApiKey();
    mutate("workspace");
    notify("success", "API key rotated.");
    return res.api_key;
  }, [notify]);

  return { workspace: data, loading: isLoading, rotateKey };
}
