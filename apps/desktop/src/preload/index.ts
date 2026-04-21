import { contextBridge, ipcRenderer } from "electron";
import type {
  ApproveResult,
  ArtifactRow,
  CreateJobArgs,
  CreateJobResult,
  DailySpend,
  Idea,
  IdeaDecision,
  IdeaStatus,
  JobDetail,
  JobEvent,
  JobSummary,
  LiveEvent,
  ManageApi,
  PerformanceRow,
  PortfolioPosition,
  RosterKind,
  RosterRow,
  RosterUpdate,
  UpsertPosition,
} from "./types.js";

const api: ManageApi = {
  createJob: (args: CreateJobArgs): Promise<CreateJobResult> =>
    ipcRenderer.invoke("jobs:create", args),
  cancelJob: (jobId: string): Promise<void> =>
    ipcRenderer.invoke("jobs:cancel", jobId),
  listJobs: (): Promise<JobSummary[]> => ipcRenderer.invoke("jobs:list"),
  getJob: (jobId: string): Promise<JobDetail> =>
    ipcRenderer.invoke("jobs:get", jobId),
  listArtifacts: (jobId: string): Promise<ArtifactRow[]> =>
    ipcRenderer.invoke("jobs:listArtifacts", jobId),
  onJobEvent: (cb: (jobId: string, event: JobEvent) => void) => {
    const listener = (
      _e: Electron.IpcRendererEvent,
      payload: { jobId: string; event: JobEvent },
    ): void => cb(payload.jobId, payload.event);
    ipcRenderer.on("job:event", listener);
    return () => ipcRenderer.removeListener("job:event", listener);
  },
  onLiveEvent: (cb: (evt: LiveEvent) => void) => {
    const listener = (
      _e: Electron.IpcRendererEvent,
      payload: LiveEvent,
    ): void => cb(payload);
    ipcRenderer.on("live:event", listener);
    return () => ipcRenderer.removeListener("live:event", listener);
  },
  listRoster: (kind: RosterKind): Promise<RosterRow[]> =>
    ipcRenderer.invoke("roster:list", kind),
  updateRosterMember: (
    kind: RosterKind,
    name: string,
    body: RosterUpdate,
  ): Promise<RosterRow> => ipcRenderer.invoke("roster:update", kind, name, body),
  listPerformance: (personaName: string): Promise<PerformanceRow[]> =>
    ipcRenderer.invoke("roster:performance", personaName),
  listPortfolio: (): Promise<PortfolioPosition[]> =>
    ipcRenderer.invoke("portfolio:list"),
  upsertPosition: (body: UpsertPosition): Promise<PortfolioPosition> =>
    ipcRenderer.invoke("portfolio:upsert", body),
  deletePosition: (id: number): Promise<void> =>
    ipcRenderer.invoke("portfolio:delete", id),
  spendToday: (): Promise<DailySpend> => ipcRenderer.invoke("spend:today"),
  listIdeas: (opts?: {
    status?: IdeaStatus | undefined;
    ideationJobId?: string | undefined;
  }): Promise<Idea[]> => ipcRenderer.invoke("ideas:list", opts ?? {}),
  decideIdea: (id: number, body: IdeaDecision): Promise<ApproveResult> =>
    ipcRenderer.invoke("ideas:decide", id, body),
  exportMemoPdf: (args: {
    title: string;
    suggestedName: string;
    contentMd: string;
    headerHtml?: string;
  }): Promise<string | null> => ipcRenderer.invoke("pdf:exportMemo", args),
};

contextBridge.exposeInMainWorld("api", api);
