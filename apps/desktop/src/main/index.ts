import { app, BrowserWindow, dialog, ipcMain } from "electron";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { writeFile } from "node:fs/promises";
import { marked } from "marked";
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
  JobDetail,
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
  "jobs:get",
  async (_evt, jobId: string): Promise<JobDetail> => {
    const res = await fetch(`${HTTP_BASE}/jobs/${jobId}`);
    if (!res.ok) throw new Error(`get_job failed: ${res.status}`);
    return (await res.json()) as JobDetail;
  },
);

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

interface ExportMemoArgs {
  title: string;
  suggestedName: string;
  contentMd: string;
  headerHtml?: string | undefined;
}

async function renderMemoHtml(args: ExportMemoArgs): Promise<string> {
  const bodyHtml = await marked.parse(args.contentMd, { gfm: true });
  // A self-signal pattern: after all <img> tags load (or error), flip the
  // document title. Main watches for that to know when to print.
  const readySignal = `
    <script>
      window.addEventListener('load', function () {
        var imgs = Array.from(document.images);
        function done() { document.title = '__ready__'; }
        if (imgs.length === 0) return done();
        var left = imgs.length;
        imgs.forEach(function (img) {
          if (img.complete) {
            if (--left === 0) done();
          } else {
            img.addEventListener('load',  function () { if (--left === 0) done(); });
            img.addEventListener('error', function () { if (--left === 0) done(); });
          }
        });
      });
    </script>
  `;
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>${escapeHtml(args.title)}</title>
    <style>
      @page { size: A4; margin: 18mm 18mm; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
          "Helvetica Neue", Arial, sans-serif;
        font-size: 11pt;
        color: #111;
        line-height: 1.45;
        margin: 0;
      }
      h1 { font-size: 18pt; margin: 0 0 0.5em 0; }
      h2 { font-size: 13pt; margin: 1.4em 0 0.4em 0; border-bottom: 1px solid #ddd; padding-bottom: 2px; }
      h3 { font-size: 11pt; margin: 1em 0 0.3em 0; }
      p { margin: 0.4em 0; }
      hr { border: 0; border-top: 1px solid #ddd; margin: 1.2em 0; }
      strong { color: #000; }
      em { color: #333; }
      table { border-collapse: collapse; margin: 0.6em 0; width: 100%; font-size: 10pt; }
      th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
      th { background: #f4f4f4; }
      code, pre {
        font-family: "SFMono-Regular", Menlo, Consolas, monospace;
        font-size: 9.5pt;
      }
      pre { background: #f6f6f6; padding: 8px; border-radius: 4px; overflow: auto; }
      img { max-width: 100%; height: auto; display: block; margin: 0.6em 0; }
      .memo-header {
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 14px;
        font-size: 10pt;
        background: #fafafa;
      }
      .memo-header .rating {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        background: #111;
        color: #fff;
        font-weight: 600;
        letter-spacing: 0.05em;
        margin-right: 10px;
      }
    </style>
    ${readySignal}
  </head>
  <body>
    ${args.headerHtml ?? ""}
    ${bodyHtml}
  </body>
</html>`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function waitForReady(win: BrowserWindow, timeoutMs = 8_000): Promise<void> {
  return new Promise<void>((resolve) => {
    const start = Date.now();
    const onTitle = (_: unknown, title: string): void => {
      if (title === "__ready__") {
        win.webContents.removeListener("page-title-updated", onTitle);
        resolve();
      }
    };
    win.webContents.on("page-title-updated", onTitle);
    // Safety: proceed after timeout even if no signal (e.g. no images).
    const poll = setInterval(() => {
      if (Date.now() - start > timeoutMs) {
        clearInterval(poll);
        win.webContents.removeListener("page-title-updated", onTitle);
        resolve();
      }
    }, 250);
  });
}

ipcMain.handle(
  "pdf:exportMemo",
  async (evt, args: ExportMemoArgs): Promise<string | null> => {
    const parent = BrowserWindow.fromWebContents(evt.sender) ?? undefined;
    const html = await renderMemoHtml(args);

    const result = await dialog.showSaveDialog(parent ?? new BrowserWindow(), {
      title: "Export memo as PDF",
      defaultPath: args.suggestedName,
      filters: [{ name: "PDF", extensions: ["pdf"] }],
    });
    if (result.canceled || !result.filePath) return null;

    const pdfWin = new BrowserWindow({
      show: false,
      webPreferences: { sandbox: true, offscreen: false },
    });
    try {
      await pdfWin.loadURL(
        "data:text/html;charset=utf-8," + encodeURIComponent(html),
      );
      await waitForReady(pdfWin);
      const pdf = await pdfWin.webContents.printToPDF({
        printBackground: true,
        pageSize: "A4",
        margins: { top: 0.7, bottom: 0.7, left: 0.7, right: 0.7 },
      });
      await writeFile(result.filePath, pdf);
      return result.filePath;
    } finally {
      pdfWin.destroy();
    }
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
