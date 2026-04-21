// Wire types shared between main, preload, and renderer.
// Mirrors apps/backend/app/schemas/*.py. CLAUDE.md §11 notes these are
// regenerated from Pydantic in a later phase; for now maintained by hand.

export type PersonaName = "buffett" | "druckenmiller" | "burry";
export type AnalystName = "valuation" | "fundamentals";
export type JobType = "research" | "committee" | "backtest";
export type JobStatus =
  | "queued"
  | "running"
  | "done"
  | "error"
  | "budget_exceeded";

export interface ResearchInputs {
  persona: PersonaName;
  ticker: string;
  prompt?: string | undefined;
}

export interface CommitteeInputs {
  ticker: string;
  prompt?: string | undefined;
  personas?: PersonaName[] | undefined;
}

export type CreateJobArgs =
  | { type: "research"; inputs: ResearchInputs; budget_usd?: number | undefined }
  | { type: "committee"; inputs: CommitteeInputs; budget_usd?: number | undefined };

export interface CreateJobResult {
  jobId: string;
}

export interface ArtifactPayload {
  id: number | null;
  job_id: string;
  kind: string;
  content_md: string | null;
  content_json: Record<string, unknown> | null;
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
  | { type: "artifact"; artifact: ArtifactPayload }
  | { type: "job_done"; cost_usd: number }
  | { type: "error"; message: string };

export interface JobSummary {
  id: string;
  type: JobType;
  status: JobStatus;
  cost_usd: number;
  budget_usd: number;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  ticker: string | null;
  persona: string | null;
}

export interface ArtifactRow {
  id: number;
  job_id: string;
  kind: string;
  content_md: string | null;
  content_json: string | null;
  created_at: string;
}

export type RosterKind = "personas" | "analysts";
export type ModelId =
  | "claude-opus-4-7"
  | "claude-sonnet-4-6"
  | "claude-haiku-4-5";

export interface RosterRow {
  id: number;
  name: string;
  prompt_template: string;
  model: ModelId;
  enabled: boolean;
  created_at: string;
}

export interface RosterUpdate {
  prompt_template?: string;
  model?: ModelId;
  enabled?: boolean;
}

export interface PerformanceRow {
  id: number;
  persona_id: number;
  period: string;
  trades: number;
  hit_rate: number | null;
  avg_return: number | null;
}

export interface ManageApi {
  createJob(args: CreateJobArgs): Promise<CreateJobResult>;
  cancelJob(jobId: string): Promise<void>;
  listJobs(): Promise<JobSummary[]>;
  listArtifacts(jobId: string): Promise<ArtifactRow[]>;
  onJobEvent(cb: (jobId: string, event: JobEvent) => void): () => void;
  listRoster(kind: RosterKind): Promise<RosterRow[]>;
  updateRosterMember(
    kind: RosterKind,
    name: string,
    body: RosterUpdate,
  ): Promise<RosterRow>;
  listPerformance(personaName: string): Promise<PerformanceRow[]>;
}

declare global {
  interface Window {
    api: ManageApi;
  }
}
