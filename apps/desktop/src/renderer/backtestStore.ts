import { create } from "zustand";
import type { ArtifactPayload, JobEvent, PersonaName } from "./types.js";

interface ActiveBacktest {
  id: string;
  persona: PersonaName;
  ticker: string;
  status: string;
  log: string;
  artifacts: ArtifactPayload[];
  costUsd: number | null;
  error: string | null;
  running: boolean;
}

interface BacktestState {
  active: ActiveBacktest | null;
  start(args: {
    persona: PersonaName;
    ticker: string;
    startDate: string;
    numSteps: number;
    stepWeeks: number;
    budgetUsd?: number | undefined;
  }): Promise<void>;
  apply(jobId: string, event: JobEvent): void;
  reset(): void;
}

function empty(id: string, persona: PersonaName, ticker: string): ActiveBacktest {
  return {
    id,
    persona,
    ticker,
    status: "starting",
    log: "",
    artifacts: [],
    costUsd: null,
    error: null,
    running: true,
  };
}

export const useBacktest = create<BacktestState>((set, get) => ({
  active: null,

  async start({ persona, ticker, startDate, numSteps, stepWeeks, budgetUsd }) {
    const cleanTicker = ticker.trim().toUpperCase();
    if (!cleanTicker) return;
    if (get().active?.running) return;

    try {
      const args: Parameters<typeof window.api.createJob>[0] = {
        type: "backtest",
        inputs: {
          persona,
          ticker: cleanTicker,
          start_date: startDate,
          num_steps: numSteps,
          step_weeks: stepWeeks,
        },
      };
      if (budgetUsd !== undefined) args.budget_usd = budgetUsd;
      const { jobId } = await window.api.createJob(args);
      set({ active: empty(jobId, persona, cleanTicker) });
    } catch (err) {
      set({
        active: {
          id: "",
          persona,
          ticker: cleanTicker,
          status: "error",
          log: "",
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
    const next: ActiveBacktest = { ...active };
    switch (event.type) {
      case "status":
        if (event.agent === "backtester") next.status = event.status;
        break;
      case "token":
        if (event.agent === "backtester") next.log = active.log + event.text;
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
