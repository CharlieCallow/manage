import { create } from "zustand";
import type { LiveEvent } from "./types.js";

/**
 * Ambient per-agent activity state. Fed from the broadcast /ws/live channel
 * via main-process IPC. Backs the Trading Floor room.
 */

export interface AgentActivity {
  name: string;
  status: string | null;
  lastJobId: string | null;
  lastText: string;        // rolling tail of most recent tokens
  tokensThisJob: number;   // how much this agent has spoken on its current job
  lastSeen: number;        // unix ms
  active: boolean;         // streaming right now (best-effort)
}

interface LiveState {
  byAgent: Record<string, AgentActivity>;
  ingest(evt: LiveEvent): void;
}

const TAIL_LEN = 160;

function emptyActivity(name: string): AgentActivity {
  return {
    name,
    status: null,
    lastJobId: null,
    lastText: "",
    tokensThisJob: 0,
    lastSeen: 0,
    active: false,
  };
}

function terminalStatus(status: string): boolean {
  return status === "done" || status === "budget_exceeded" || status === "error";
}

export const useLive = create<LiveState>((set, get) => ({
  byAgent: {},

  ingest(evt) {
    const { jobId } = evt;
    const ev = evt.event;
    if (!("agent" in ev)) return; // job_done / error don't name an agent
    const name = ev.agent;
    const now = Date.now();
    const prev = get().byAgent[name] ?? emptyActivity(name);
    const next: AgentActivity = { ...prev, name, lastSeen: now };

    if (prev.lastJobId !== jobId) {
      next.lastJobId = jobId;
      next.lastText = "";
      next.tokensThisJob = 0;
    }

    if (ev.type === "token") {
      next.lastText = (prev.lastText + ev.text).slice(-TAIL_LEN);
      next.tokensThisJob = prev.tokensThisJob + 1;
      next.active = true;
    } else if (ev.type === "status") {
      next.status = ev.status;
      next.active = !terminalStatus(ev.status);
    }

    set({ byAgent: { ...get().byAgent, [name]: next } });
  },
}));
