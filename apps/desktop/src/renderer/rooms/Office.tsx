import { useCallback, useEffect, useState } from "react";
import { JobList } from "../components/JobList.js";
import { PortfolioTable } from "../components/PortfolioTable.js";
import { SpendWidget } from "../components/SpendWidget.js";
import { useResearch } from "../store.js";
import type { DailySpend, PortfolioPosition } from "../types.js";

const SPEND_REFRESH_MS = 15_000;

export function Office(): JSX.Element {
  const jobs = useResearch((s) => s.jobs);
  const loadJobs = useResearch((s) => s.loadJobs);

  const [positions, setPositions] = useState<PortfolioPosition[]>([]);
  const [spend, setSpend] = useState<DailySpend | null>(null);

  const loadPositions = useCallback(async () => {
    try {
      setPositions(await window.api.listPortfolio());
    } catch {
      // non-fatal; retry on next tick
    }
  }, []);

  const loadSpend = useCallback(async () => {
    try {
      setSpend(await window.api.spendToday());
    } catch {
      // non-fatal
    }
  }, []);

  useEffect(() => {
    void loadPositions();
    void loadSpend();
    void loadJobs();
    const t = window.setInterval(() => {
      void loadSpend();
      void loadJobs();
    }, SPEND_REFRESH_MS);
    return () => window.clearInterval(t);
  }, [loadPositions, loadSpend, loadJobs]);

  const finishedCount = jobs.filter((j) => j.status === "done").length;
  const activeCount = jobs.filter(
    (j) => j.status === "running" || j.status === "queued",
  ).length;

  return (
    <div className="grid grid-cols-[1fr_20rem] gap-6 min-w-0">
      <main className="flex flex-col gap-6 min-w-0">
        <div className="grid grid-cols-3 gap-3 text-sm">
          <Stat label="Finished jobs" value={String(finishedCount)} />
          <Stat label="Active / queued" value={String(activeCount)} />
          <Stat
            label="Positions"
            value={String(positions.length)}
          />
        </div>

        <SpendWidget spend={spend} />

        <PortfolioTable positions={positions} onChange={loadPositions} />
      </main>

      <aside className="flex flex-col gap-3 min-w-0">
        <h2 className="text-xs text-neutral-400 uppercase tracking-wide">
          Recent jobs
        </h2>
        <JobList jobs={jobs} activeId={null} />
      </aside>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="border border-neutral-800 rounded px-4 py-3 bg-neutral-950/60">
      <div className="text-xs text-neutral-500 uppercase tracking-wide">
        {label}
      </div>
      <div className="text-2xl font-mono text-neutral-100">{value}</div>
    </div>
  );
}
