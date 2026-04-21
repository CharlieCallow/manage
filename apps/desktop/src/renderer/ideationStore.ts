import { create } from "zustand";
import type { Idea, JobEvent } from "./types.js";

interface ActiveIdeation {
  id: string;
  framing: string;
  statusByAgent: Record<string, string>;
  tokensByAgent: Record<string, string>;
  costUsd: number | null;
  error: string | null;
  running: boolean;
}

interface IdeationState {
  active: ActiveIdeation | null;
  pending: Idea[];
  start(args: {
    framing?: string | undefined;
    numPerPersona: number;
    budgetUsd?: number | undefined;
  }): Promise<void>;
  apply(jobId: string, event: JobEvent): void;
  refreshPending(): Promise<void>;
  afterDecision(ideaId: number): void;
  reset(): void;
}

function emptyActive(id: string, framing: string): ActiveIdeation {
  return {
    id,
    framing,
    statusByAgent: {},
    tokensByAgent: {},
    costUsd: null,
    error: null,
    running: true,
  };
}

export const useIdeation = create<IdeationState>((set, get) => ({
  active: null,
  pending: [],

  async start({ framing, numPerPersona, budgetUsd }) {
    if (get().active?.running) return;
    const cleanFraming = framing?.trim() ?? "";

    try {
      const args: Parameters<typeof window.api.createJob>[0] = {
        type: "ideation",
        inputs: {
          num_per_persona: numPerPersona,
          ...(cleanFraming ? { framing: cleanFraming } : {}),
        },
      };
      if (budgetUsd !== undefined) args.budget_usd = budgetUsd;
      const { jobId } = await window.api.createJob(args);
      set({ active: emptyActive(jobId, cleanFraming) });
    } catch (err) {
      set({
        active: {
          id: "",
          framing: cleanFraming,
          statusByAgent: {},
          tokensByAgent: {},
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
    const next: ActiveIdeation = { ...active };
    switch (event.type) {
      case "status":
        next.statusByAgent = {
          ...active.statusByAgent,
          [event.agent]: event.status,
        };
        break;
      case "token":
        next.tokensByAgent = {
          ...active.tokensByAgent,
          [event.agent]:
            (active.tokensByAgent[event.agent] ?? "") + event.text,
        };
        break;
      case "artifact":
        // Candidates were persisted by the graph; pull the fresh list.
        void get().refreshPending();
        break;
      case "job_done":
        next.costUsd = event.cost_usd;
        next.running = false;
        void get().refreshPending();
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

  async refreshPending() {
    try {
      const pending = await window.api.listIdeas({ status: "pending" });
      set({ pending });
    } catch {
      // non-fatal
    }
  },

  afterDecision(ideaId) {
    set({ pending: get().pending.filter((i) => i.id !== ideaId) });
  },

  reset() {
    set({ active: null });
  },
}));
