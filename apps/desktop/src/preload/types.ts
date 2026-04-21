// Wire types shared between main, preload, and renderer.
// Mirrors apps/backend/app/schemas/*.py. CLAUDE.md §11 notes these are
// regenerated from Pydantic in a later phase; for now maintained by hand.

export type PersonaName = "buffett" | "druckenmiller" | "burry";
export type AnalystName = "valuation" | "fundamentals";
export type JobType = "research" | "committee" | "backtest" | "ideation";
export type JobStatus =
  | "queued"
  | "running"
  | "done"
  | "error"
  | "budget_exceeded";

export type ReportStyle = "classic" | "citrini";

export interface ResearchInputs {
  persona: PersonaName;
  ticker: string;
  prompt?: string | undefined;
  style?: ReportStyle | undefined;
}

export interface CommitteeInputs {
  ticker: string;
  prompt?: string | undefined;
  personas?: PersonaName[] | undefined;
}

export interface BacktestInputs {
  persona: PersonaName;
  ticker: string;
  start_date: string; // YYYY-MM-DD
  num_steps: number;
  step_weeks: number;
}

export interface IdeationInputs {
  framing?: string | undefined;
  personas?: PersonaName[] | undefined;
  num_per_persona: number;
}

export type CreateJobArgs =
  | { type: "research"; inputs: ResearchInputs; budget_usd?: number | undefined }
  | { type: "committee"; inputs: CommitteeInputs; budget_usd?: number | undefined }
  | { type: "backtest"; inputs: BacktestInputs; budget_usd?: number | undefined }
  | { type: "ideation"; inputs: IdeationInputs; budget_usd?: number | undefined };

export type IdeaStatus = "pending" | "approved" | "dismissed";

export interface Idea {
  id: number;
  ideation_job_id: string;
  persona: PersonaName;
  ticker: string;
  thesis: string;
  status: IdeaStatus;
  research_job_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface IdeaDecision {
  status: "approved" | "dismissed";
}

export interface ApproveResult {
  idea: Idea;
  research_job_id: string | null;
}

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

export interface JobDetail {
  id: string;
  type: JobType;
  status: JobStatus;
  cost_usd: number;
  budget_usd: number;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  inputs: Record<string, unknown>;
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

export interface PortfolioPosition {
  id: number;
  ticker: string;
  qty: number;
  avg_price: number;
  updated_at: string;
}

export interface UpsertPosition {
  ticker: string;
  qty: number;
  avg_price: number;
}

export interface ModelSpend {
  model: string;
  cost: number;
  input_tokens: number;
  output_tokens: number;
  calls: number;
}

export interface DailySpend {
  total_usd: number;
  input_tokens: number;
  output_tokens: number;
  by_model: ModelSpend[];
  daily_cap_usd: number;
}

export interface LiveEvent {
  jobId: string;
  event: JobEvent;
}

export interface ManageApi {
  createJob(args: CreateJobArgs): Promise<CreateJobResult>;
  cancelJob(jobId: string): Promise<void>;
  listJobs(): Promise<JobSummary[]>;
  getJob(jobId: string): Promise<JobDetail>;
  listArtifacts(jobId: string): Promise<ArtifactRow[]>;
  onJobEvent(cb: (jobId: string, event: JobEvent) => void): () => void;
  onLiveEvent(cb: (evt: LiveEvent) => void): () => void;
  listRoster(kind: RosterKind): Promise<RosterRow[]>;
  updateRosterMember(
    kind: RosterKind,
    name: string,
    body: RosterUpdate,
  ): Promise<RosterRow>;
  listPerformance(personaName: string): Promise<PerformanceRow[]>;
  listPortfolio(): Promise<PortfolioPosition[]>;
  upsertPosition(body: UpsertPosition): Promise<PortfolioPosition>;
  deletePosition(id: number): Promise<void>;
  spendToday(): Promise<DailySpend>;
  listIdeas(opts?: {
    status?: IdeaStatus | undefined;
    ideationJobId?: string | undefined;
  }): Promise<Idea[]>;
  decideIdea(id: number, body: IdeaDecision): Promise<ApproveResult>;
}

declare global {
  interface Window {
    api: ManageApi;
  }
}
