import { create } from "zustand";
import type { JobEvent } from "./types.js";

interface DebugPanelState {
  jobId: string | null;
  tokens: string;
  status: string;
  error: string | null;
  costUsd: number | null;
  running: boolean;
  start(prompt: string): Promise<void>;
  reset(): void;
  apply(event: JobEvent): void;
}

export const useDebugPanel = create<DebugPanelState>((set, get) => ({
  jobId: null,
  tokens: "",
  status: "",
  error: null,
  costUsd: null,
  running: false,

  async start(prompt: string) {
    if (get().running) return;
    set({
      jobId: null,
      tokens: "",
      status: "starting",
      error: null,
      costUsd: null,
      running: true,
    });
    try {
      const { jobId } = await window.api.createJob({
        type: "research",
        inputs: { persona: "buffett", prompt },
      });
      set({ jobId });
    } catch (err) {
      set({
        running: false,
        status: "error",
        error: err instanceof Error ? err.message : String(err),
      });
    }
  },

  reset() {
    set({
      jobId: null,
      tokens: "",
      status: "",
      error: null,
      costUsd: null,
      running: false,
    });
  },

  apply(event: JobEvent) {
    switch (event.type) {
      case "token":
        set((s) => ({ tokens: s.tokens + event.text }));
        return;
      case "status":
        set({ status: event.status });
        return;
      case "error":
        set({ error: event.message, running: false });
        return;
      case "job_done":
        set({ costUsd: event.cost_usd, running: false });
        return;
      case "tool_call":
      case "tool_result":
      case "artifact":
        // Phase 0 debug panel doesn't render these yet.
        return;
    }
  },
}));
