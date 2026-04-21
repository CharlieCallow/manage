import { create } from "zustand";
import type { ArtifactPayload, JobEvent } from "./types.js";

type AgentName = string;

interface ActiveCommittee {
  id: string;
  ticker: string;
  tokensByAgent: Record<AgentName, string>;
  statusByAgent: Record<AgentName, string>;
  artifacts: ArtifactPayload[];
  costUsd: number | null;
  error: string | null;
  running: boolean;
}

interface CommitteeState {
  active: ActiveCommittee | null;
  start(args: {
    ticker: string;
    prompt?: string | undefined;
    budgetUsd?: number | undefined;
  }): Promise<void>;
  apply(jobId: string, event: JobEvent): void;
  reset(): void;
}

function emptyActive(id: string, ticker: string): ActiveCommittee {
  return {
    id,
    ticker,
    tokensByAgent: {},
    statusByAgent: {},
    artifacts: [],
    costUsd: null,
    error: null,
    running: true,
  };
}

export const useCommittee = create<CommitteeState>((set, get) => ({
  active: null,

  async start({ ticker, prompt, budgetUsd }) {
    const cleanTicker = ticker.trim().toUpperCase();
    if (!cleanTicker) return;
    if (get().active?.running) return;

    try {
      const inputs: { ticker: string; prompt?: string } = { ticker: cleanTicker };
      if (prompt) inputs.prompt = prompt;
      const args: {
        type: "committee";
        inputs: typeof inputs;
        budget_usd?: number;
      } = { type: "committee", inputs };
      if (budgetUsd !== undefined) args.budget_usd = budgetUsd;
      const { jobId } = await window.api.createJob(args);
      set({ active: emptyActive(jobId, cleanTicker) });
    } catch (err) {
      set({
        active: {
          id: "",
          ticker: cleanTicker,
          tokensByAgent: {},
          statusByAgent: {},
          artifacts: [],
          costUsd: null,
          error: err instanceof Error ? err.message : String(err),
          running: false,
        },
      });
    }
  },

  apply(jobId, event) {
    const active = get().active;
    if (!active || active.id !== jobId) return;

    const next: ActiveCommittee = { ...active };
    switch (event.type) {
      case "token":
        next.tokensByAgent = {
          ...active.tokensByAgent,
          [event.agent]: (active.tokensByAgent[event.agent] ?? "") + event.text,
        };
        break;
      case "status":
        next.statusByAgent = {
          ...active.statusByAgent,
          [event.agent]: event.status,
        };
        break;
      case "artifact":
        next.artifacts = [...active.artifacts, event.artifact];
        break;
      case "job_done":
        next.costUsd = event.cost_usd;
        next.running = false;
        break;
      case "error":
        next.error = event.message;
        next.running = false;
        break;
      case "tool_call":
      case "tool_result":
        return;
    }
    set({ active: next });
  },

  reset() {
    set({ active: null });
  },
}));
