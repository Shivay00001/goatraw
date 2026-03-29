/**
 * GoatRaw — Zustand Global Store
 * Manages auth state, active tasks, and UI state.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { User, Task, TaskResult, TaskStatus } from "@/types";
import { setToken, clearToken } from "@/services/api";

// ── Auth Slice ────────────────────────────────────────────────
interface AuthState {
  user: User | null;
  token: string;
  isAuthenticated: boolean;
  setAuth: (user: User, token: string) => void;
  logout: () => void;
}

// ── Task Slice ────────────────────────────────────────────────
interface ActiveTask {
  id: string;
  goal: string;
  status: TaskStatus;
  agentType: string;
  result?: TaskResult;
  createdAt: string;
}

interface TaskState {
  activeTasks: Record<string, ActiveTask>;
  recentTasks: ActiveTask[];
  addTask: (task: ActiveTask) => void;
  updateTaskStatus: (id: string, status: TaskStatus, result?: TaskResult) => void;
  removeTask: (id: string) => void;
}

// ── UI Slice ──────────────────────────────────────────────────
interface UIState {
  sidebarOpen: boolean;
  theme: "dark";
  notifications: Array<{ id: string; type: "success" | "error" | "info"; message: string }>;
  toggleSidebar: () => void;
  addNotification: (type: "success" | "error" | "info", message: string) => void;
  removeNotification: (id: string) => void;
}

// ── Combined Store ────────────────────────────────────────────
type GoatRawStore = AuthState & TaskState & UIState;

export const useStore = create<GoatRawStore>()(
  persist(
    (set, get) => ({
      // ── Auth ──────────────────────────────────────────────
      user: null,
      token: "",
      isAuthenticated: false,

      setAuth: (user, token) => {
        setToken(token);
        set({ user, token, isAuthenticated: true });
      },

      logout: () => {
        clearToken();
        set({ user: null, token: "", isAuthenticated: false });
        if (typeof window !== "undefined") window.location.href = "/auth/login";
      },

      // ── Tasks ─────────────────────────────────────────────
      activeTasks: {},
      recentTasks: [],

      addTask: (task) => {
        set((s) => ({
          activeTasks: { ...s.activeTasks, [task.id]: task },
          recentTasks: [task, ...s.recentTasks].slice(0, 20),
        }));
      },

      updateTaskStatus: (id, status, result) => {
        set((s) => {
          const task = s.activeTasks[id];
          if (!task) return s;
          const updated = { ...task, status, ...(result ? { result } : {}) };
          const activeTasks = { ...s.activeTasks, [id]: updated };
          const recentTasks = s.recentTasks.map((t) => (t.id === id ? updated : t));
          // Remove from active if done
          if (status === "completed" || status === "failed" || status === "cancelled") {
            delete activeTasks[id];
          }
          return { activeTasks, recentTasks };
        });
      },

      removeTask: (id) => {
        set((s) => {
          const { [id]: _, ...rest } = s.activeTasks;
          return { activeTasks: rest };
        });
      },

      // ── UI ────────────────────────────────────────────────
      sidebarOpen: true,
      theme: "dark",
      notifications: [],

      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

      addNotification: (type, message) => {
        const id = Math.random().toString(36).slice(2, 8);
        set((s) => ({ notifications: [...s.notifications, { id, type, message }] }));
        setTimeout(() => get().removeNotification(id), 4500);
      },

      removeNotification: (id) =>
        set((s) => ({ notifications: s.notifications.filter((n) => n.id !== id) })),
    }),
    {
      name: "goatraw-store",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ user: s.user, token: s.token, isAuthenticated: s.isAuthenticated }),
    }
  )
);

// ── Convenience selectors ─────────────────────────────────────
export const useUser          = () => useStore((s) => s.user);
export const useIsAuth        = () => useStore((s) => s.isAuthenticated);
export const useActiveTasks   = () => useStore((s) => Object.values(s.activeTasks));
export const useRecentTasks   = () => useStore((s) => s.recentTasks);
export const useNotifications = () => useStore((s) => s.notifications);
export const useNotify        = () => useStore((s) => s.addNotification);
