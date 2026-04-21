import { contextBridge, ipcRenderer } from "electron";
import type {
  ArtifactRow,
  CreateJobArgs,
  CreateJobResult,
  JobEvent,
  JobSummary,
  ManageApi,
} from "./types.js";

const api: ManageApi = {
  createJob: (args: CreateJobArgs): Promise<CreateJobResult> =>
    ipcRenderer.invoke("jobs:create", args),
  cancelJob: (jobId: string): Promise<void> =>
    ipcRenderer.invoke("jobs:cancel", jobId),
  listJobs: (): Promise<JobSummary[]> => ipcRenderer.invoke("jobs:list"),
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
};

contextBridge.exposeInMainWorld("api", api);
