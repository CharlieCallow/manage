import { app, BrowserWindow, ipcMain } from "electron";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { WebSocket } from "ws";
import type {
  ApproveResult,
  ArtifactRow,
  CreateJobArgs,
  CreateJobResult,
  DailySpend,
  Idea,
  IdeaDecision,
  IdeaStatus,
  JobEvent,
  JobSummary,
  LiveEvent,
  PerformanceRow,
  PortfolioPosition,
  RosterKind,
  RosterRow,
  RosterUpdate,
  UpsertPosition,
} from "../preload/types.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const BACKEND_HOST = process.env.BACKEND_HOST ?? "127.0.0.1";
const BACKEND_PORT = process.env.BACKEND_PORT ?? "8787";
const HTTP_BASE = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const WS_BASE = `ws://${BACKEND_HOST}:${BACKEND_PORT}`;

const openSockets = new Map<string, WebSocket>();
let liveSocket: WebSocket | null = null;
const LIVE_RECONNECT_MS = 2000;

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    backgroundColor: "#0a0a0a",
    webPreferences: {
      preload: join(__dirname, "../preload/index.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  if (process.env["ELECTRON_RENDERER_URL"]) {
    void win.loadURL(process.env["ELECTRON_RENDERER_URL"]);
  } else {
    void win.loadFile(join(__dirname, "../../dist/index.html"));
  }
  return win;
}

function forward(win: BrowserWindow, jobId: string, event: JobEvent): void {
  if (!win.isDestroyed()) {
    win.webContents.send("job:event", { jobId, event });
  }
}

function broadcastLive(evt: LiveEvent): void {
  for (const win of BrowserWindow.getAllWindows()) {
    if (!win.isDestroyed()) {
      win.webContents.send("live:event", evt);
    }
  }
}

function connectLive(): void {
  const ws = new WebSocket(`${WS_BASE}/ws/live`);
  liveSocket = ws;
  ws.on("open", () => {
    // Clear handler — connection will naturally close if backend shuts down.
  });
  ws.on("message", (raw) => {
    try {
      const payload = JSON.parse(raw.toString()) as {
        job_id: string;
        event: JobEvent;
      };
      broadcastLive({ jobId: payload.job_id, event: payload.event });
    } catch {
      // Swallow malformed broadcast events — they're non-authoritative.
    }
  });
  ws.on("close", () => {
    liveSocket = null;
    setTimeout(connectLive, LIVE_RECONNECT_MS);
  });
  ws.on("error", () => {
    ws.close();
  });
}

ipcMain.handle(
  "jobs:create",
  async (evt, args: CreateJobArgs): Promise<CreateJobResult> => {
    const win = BrowserWindow.fromWebContents(evt.sender);
    if (!win) throw new Error("no window for sender");

    const res = await fetch(`${HTTP_BASE}/jobs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(args),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`backend rejected job: ${res.status} ${text}`);
    }
    const body = (await res.json()) as { job_id: string };

    const ws = new WebSocket(`${WS_BASE}/ws/jobs/${body.job_id}`);
    openSockets.set(body.job_id, ws);

    ws.on("message", (raw) => {
      try {
        const event = JSON.parse(raw.toString()) as JobEvent;
        forward(win, body.job_id, event);
      } catch (err) {
        forward(win, body.job_id, {
          type: "error",
          message: `malformed event: ${String(err)}`,
        });
      }
    });
    ws.on("close", () => {
      openSockets.delete(body.job_id);
    });
    ws.on("error", (err) => {
      forward(win, body.job_id, {
        type: "error",
        message: `websocket error: ${err.message}`,
      });
    });

    return { jobId: body.job_id };
  },
);

ipcMain.handle("jobs:cancel", (_evt, jobId: string): void => {
  const ws = openSockets.get(jobId);
  if (ws) {
    ws.close();
    openSockets.delete(jobId);
  }
});

ipcMain.handle("jobs:list", async (): Promise<JobSummary[]> => {
  const res = await fetch(`${HTTP_BASE}/jobs`);
  if (!res.ok) throw new Error(`list_jobs failed: ${res.status}`);
  return (await res.json()) as JobSummary[];
});

ipcMain.handle(
  "jobs:listArtifacts",
  async (_evt, jobId: string): Promise<ArtifactRow[]> => {
    const res = await fetch(`${HTTP_BASE}/jobs/${jobId}/artifacts`);
    if (!res.ok) throw new Error(`list_artifacts failed: ${res.status}`);
    return (await res.json()) as ArtifactRow[];
  },
);

ipcMain.handle(
  "roster:list",
  async (_evt, kind: RosterKind): Promise<RosterRow[]> => {
    const res = await fetch(`${HTTP_BASE}/${kind}`);
    if (!res.ok) throw new Error(`roster list failed: ${res.status}`);
    return (await res.json()) as RosterRow[];
  },
);

ipcMain.handle(
  "roster:update",
  async (
    _evt,
    kind: RosterKind,
    name: string,
    body: RosterUpdate,
  ): Promise<RosterRow> => {
    const res = await fetch(`${HTTP_BASE}/${kind}/${encodeURIComponent(name)}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`roster update failed: ${res.status} ${text}`);
    }
    return (await res.json()) as RosterRow;
  },
);

ipcMain.handle(
  "roster:performance",
  async (_evt, personaName: string): Promise<PerformanceRow[]> => {
    const res = await fetch(
      `${HTTP_BASE}/personas/${encodeURIComponent(personaName)}/performance`,
    );
    if (!res.ok) throw new Error(`performance fetch failed: ${res.status}`);
    return (await res.json()) as PerformanceRow[];
  },
);

ipcMain.handle("portfolio:list", async (): Promise<PortfolioPosition[]> => {
  const res = await fetch(`${HTTP_BASE}/portfolio`);
  if (!res.ok) throw new Error(`portfolio list failed: ${res.status}`);
  return (await res.json()) as PortfolioPosition[];
});

ipcMain.handle(
  "portfolio:upsert",
  async (_evt, body: UpsertPosition): Promise<PortfolioPosition> => {
    const ticker = body.ticker.trim().toUpperCase();
    const res = await fetch(
      `${HTTP_BASE}/portfolio/${encodeURIComponent(ticker)}`,
      {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...body, ticker }),
      },
    );
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`portfolio upsert failed: ${res.status} ${text}`);
    }
    return (await res.json()) as PortfolioPosition;
  },
);

ipcMain.handle("portfolio:delete", async (_evt, id: number): Promise<void> => {
  const res = await fetch(`${HTTP_BASE}/portfolio/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`portfolio delete failed: ${res.status}`);
});

ipcMain.handle("spend:today", async (): Promise<DailySpend> => {
  const res = await fetch(`${HTTP_BASE}/spend/today`);
  if (!res.ok) throw new Error(`spend_today failed: ${res.status}`);
  return (await res.json()) as DailySpend;
});

ipcMain.handle(
  "ideas:list",
  async (
    _evt,
    opts: { status?: IdeaStatus; ideationJobId?: string },
  ): Promise<Idea[]> => {
    const params = new URLSearchParams();
    if (opts?.status) params.set("status", opts.status);
    if (opts?.ideationJobId) params.set("ideation_job_id", opts.ideationJobId);
    const q = params.toString();
    const res = await fetch(`${HTTP_BASE}/ideas${q ? `?${q}` : ""}`);
    if (!res.ok) throw new Error(`ideas list failed: ${res.status}`);
    return (await res.json()) as Idea[];
  },
);

ipcMain.handle(
  "ideas:decide",
  async (_evt, id: number, body: IdeaDecision): Promise<ApproveResult> => {
    const res = await fetch(`${HTTP_BASE}/ideas/${id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`ideas decide failed: ${res.status} ${text}`);
    }
    return (await res.json()) as ApproveResult;
  },
);

app.whenReady().then(() => {
  createWindow();
  connectLive();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  for (const ws of openSockets.values()) ws.close();
  openSockets.clear();
  if (liveSocket) {
    liveSocket.close();
    liveSocket = null;
  }
  if (process.platform !== "darwin") app.quit();
});
