import { create } from "zustand";
import type {
  ArtifactPayload,
  JobEvent,
  JobSummary,
  PersonaName,
} from "./types.js";

type AgentName = string;

interface ActiveJob {
  id: string;
  ticker: string;
  persona: PersonaName;
  tokensByAgent: Record<AgentName, string>;
  statusByAgent: Record<AgentName, string>;
  artifacts: ArtifactPayload[];
  costUsd: number | null;
  error: string | null;
  running: boolean;
}

interface ResearchState {
  active: ActiveJob | null;
  jobs: JobSummary[];
  start(args: {
    persona: PersonaName;
    ticker: string;
    prompt?: string | undefined;
    budgetUsd?: number | undefined;
  }): Promise<void>;
  apply(jobId: string, event: JobEvent): void;
  loadJobs(): Promise<void>;
  reset(): void;
}

function emptyActive(
  id: string,
  ticker: string,
  persona: PersonaName,
): ActiveJob {
  return {
    id,
    ticker,
    persona,
    tokensByAgent: {},
    statusByAgent: {},
    artifacts: [],
    costUsd: null,
    error: null,
    running: true,
  };
}

export const useResearch = create<ResearchState>((set, get) => ({
  active: null,
  jobs: [],

  async start({ persona, ticker, prompt, budgetUsd }) {
    const cleanTicker = ticker.trim().toUpperCase();
    if (!cleanTicker) return;
    if (get().active?.running) return;

    try {
      const inputs: {
        persona: PersonaName;
        ticker: string;
        prompt?: string;
      } = { persona, ticker: cleanTicker };
      if (prompt) inputs.prompt = prompt;
      const args: {
        type: "research";
        inputs: typeof inputs;
        budget_usd?: number;
      } = { type: "research", inputs };
      if (budgetUsd !== undefined) args.budget_usd = budgetUsd;
      const { jobId } = await window.api.createJob(args);
      set({ active: emptyActive(jobId, cleanTicker, persona) });
      void get().loadJobs();
    } catch (err) {
      set({
        active: {
          id: "",
          ticker: cleanTicker,
          persona,
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

    const next: ActiveJob = { ...active };
    switch (event.type) {
      case "token":
        next.tokensByAgent = {
          ...active.tokensByAgent,
          [event.agent]:
            (active.tokensByAgent[event.agent] ?? "") + event.text,
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
        void get().loadJobs();
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

  async loadJobs() {
    try {
      const jobs = await window.api.listJobs();
      set({ jobs });
    } catch {
      // Benign — jobs list will retry on next event.
    }
  },

  reset() {
    set({ active: null });
  },
}));
