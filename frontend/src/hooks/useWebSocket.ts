/**
 * GoatRaw — useWebSocket Hook
 * Real-time task status updates via WebSocket.
 * Automatically reconnects, sends pings, and updates the task store.
 */

"use client";
import { useEffect, useRef, useCallback, useState } from "react";
import { useStore, useIsAuth } from "@/store";
import { getToken } from "@/services/api";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
  .replace(/^https?/, (m) => (m === "https" ? "wss" : "ws"));

type WSStatus = "disconnected" | "connecting" | "connected" | "error";

export function useWebSocket() {
  const wsRef    = useRef<WebSocket | null>(null);
  const reconnect= useRef<ReturnType<typeof setTimeout> | null>(null);
  const [status, setStatus]  = useState<WSStatus>("disconnected");
  const user     = useStore((s) => s.user);
  const isAuth   = useIsAuth();
  const updateTask = useStore((s) => s.updateTaskStatus);
  const notify   = useStore((s) => s.addNotification);

  const connect = useCallback(() => {
    if (!isAuth || !user?.id) return;
    const token = getToken();
    if (!token) return;

    setStatus("connecting");
    const url = `${WS_BASE}/ws/${user.id}?token=${token}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === "task_update") {
          updateTask(msg.task_id, msg.status);
        } else if (msg.type === "task_result") {
          updateTask(msg.task_id, "completed", msg);
          notify("success", "Task completed!");
        } else if (msg.type === "heartbeat") {
          if (msg.status === "ACTION_NEEDED") {
            notify("info", `Heartbeat: ${msg.message}`);
          }
        }
        // ping messages are silently ignored
      } catch {
        // Non-JSON message — ignore
      }
    };

    ws.onclose = (event) => {
      setStatus("disconnected");
      wsRef.current = null;
      // Reconnect after 3s unless intentional close
      if (event.code !== 1000 && event.code !== 4001) {
        reconnect.current = setTimeout(connect, 3000);
      }
    };

    ws.onerror = () => {
      setStatus("error");
    };
  }, [isAuth, user?.id, updateTask, notify]);

  useEffect(() => {
    if (isAuth) connect();
    return () => {
      if (reconnect.current) clearTimeout(reconnect.current);
      if (wsRef.current) wsRef.current.close(1000, "component unmounted");
    };
  }, [isAuth, connect]);

  const trackTask = useCallback((taskId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "track_task", task_id: taskId }));
    }
  }, []);

  return { status, trackTask, reconnect: connect };
}

// ── Status indicator component ────────────────────────────────
export function WSStatusDot({ status }: { status: WSStatus }) {
  const colors: Record<WSStatus, string> = {
    connected:    "bg-green",
    connecting:   "bg-yellow dot-pulse",
    disconnected: "bg-muted",
    error:        "bg-red",
  };
  return (
    <span className="flex items-center gap-1.5 text-[11px] font-mono text-muted">
      <span className={`w-1.5 h-1.5 rounded-full ${colors[status]}`} />
      {status}
    </span>
  );
}
