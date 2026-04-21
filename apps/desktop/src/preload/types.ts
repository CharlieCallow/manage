// Wire types shared between main, preload, and renderer.
// Mirrors apps/backend/app/schemas/events.py. CLAUDE.md §11 notes these are
// regenerated from Pydantic in Phase 1+; for now they're maintained by hand.

export type PersonaName = "buffett";
export type JobType = "research" | "committee" | "backtest";

export interface ResearchInputs {
  persona: PersonaName;
  prompt: string;
}

export interface CreateJobArgs {
  type: JobType;
  inputs: ResearchInputs;
  budget_usd?: number;
}

export interface CreateJobResult {
  jobId: string;
}

export type JobEvent =
  | { type: "token"; agent: string; text: string }
  | {
      type: "tool_call";
      agent: string;
      name: string;
      input: Record<string, unknown>;
    }
  | {
      type: "tool_result";
      agent: string;
      name: string;
      output: Record<string, unknown>;
    }
  | { type: "status"; agent: string; status: string }
  | {
      type: "artifact";
      artifact: {
        id: number | null;
        job_id: string;
        kind: string;
        content_md: string | null;
        content_json: Record<string, unknown> | null;
      };
    }
  | { type: "job_done"; cost_usd: number }
  | { type: "error"; message: string };

export interface ManageApi {
  createJob(args: CreateJobArgs): Promise<CreateJobResult>;
  cancelJob(jobId: string): Promise<void>;
  onJobEvent(cb: (jobId: string, event: JobEvent) => void): () => void;
}

declare global {
  interface Window {
    api: ManageApi;
  }
}
