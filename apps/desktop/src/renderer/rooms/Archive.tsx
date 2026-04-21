import { useCallback, useEffect, useMemo, useState } from "react";
import { JobDetail } from "../components/JobDetail.js";
import { useNav } from "../navStore.js";
import type { JobSummary, JobType } from "../types.js";

const FILTERS: { id: JobType | "all"; label: string }[] = [
  { id: "all", label: "All" },
  { id: "research", label: "Research" },
  { id: "committee", label: "Committee" },
  { id: "backtest", label: "Backtest" },
  { id: "ideation", label: "Ideation" },
];

export function Archive(): JSX.Element {
  const selectedJobId = useNav((s) => s.selectedJobId);
  const openJob = useNav((s) => s.openJob);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [filter, setFilter] = useState<JobType | "all">("all");
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setJobs(await window.api.listJobs());
    } catch {
      // non-fatal
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const filtered = useMemo(
    () => (filter === "all" ? jobs : jobs.filter((j) => j.type === filter)),
    [filter, jobs],
  );

  // If we have a selected job but it isn't in the list yet (e.g. just
  // submitted), still render the detail pane for it.
  const selectedExists = selectedJobId
    ? jobs.some((j) => j.id === selectedJobId)
    : false;

  return (
    <div className="grid grid-cols-[22rem_1fr] gap-6 min-w-0">
      <aside className="flex flex-col gap-2 min-w-0">
        <div className="flex gap-1 bg-neutral-900 rounded p-1 border border-neutral-800 text-xs">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              className={`flex-1 px-2 py-1 rounded ${
                filter === f.id
                  ? "bg-neutral-800 text-neutral-100"
                  : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => void reload()}
          className="text-xs text-neutral-500 hover:text-neutral-300 px-2 py-1 self-end"
        >
          {loading ? "refreshing…" : "refresh"}
        </button>
        <ul className="flex flex-col gap-1 overflow-y-auto max-h-[78vh]">
          {filtered.length === 0 ? (
            <li className="text-xs text-neutral-600 px-2 py-4">
              No jobs match this filter.
            </li>
          ) : (
            filtered.map((j) => (
              <li key={j.id}>
                <button
                  type="button"
                  onClick={() => openJob(j.id)}
                  className={`w-full text-left px-3 py-2 rounded text-xs border ${
                    selectedJobId === j.id
                      ? "border-amber-600 bg-amber-500/10"
                      : "border-neutral-800 bg-neutral-900/60 hover:border-neutral-700"
                  }`}
                >
                  <div className="flex justify-between items-baseline">
                    <span className="font-mono font-semibold text-neutral-100">
                      {j.ticker ?? j.type}
                    </span>
                    <span className={statusColor(j.status)}>{j.status}</span>
                  </div>
                  <div className="flex justify-between text-neutral-500 mt-0.5">
                    <span className="truncate">
                      {j.persona ?? j.type}
                    </span>
                    <span className="font-mono">
                      ${j.cost_usd.toFixed(4)}
                    </span>
                  </div>
                  <div className="text-neutral-600 text-[10px] font-mono mt-0.5">
                    {j.id.slice(0, 8)}
                  </div>
                </button>
              </li>
            ))
          )}
        </ul>
      </aside>

      <main className="min-w-0">
        {selectedJobId ? (
          <JobDetail key={selectedJobId} jobId={selectedJobId} />
        ) : (
          <div className="text-sm text-neutral-500 border border-neutral-800 rounded bg-neutral-950/60 px-4 py-6">
            Pick a job on the left to see inputs, artifacts, and cost.
          </div>
        )}
        {selectedJobId && !selectedExists && !loading && (
          <div className="mt-3 text-xs text-neutral-500">
            (This job isn't in the list yet — it may have just been started.
            Click refresh to update.)
          </div>
        )}
      </main>
    </div>
  );
}

function statusColor(status: string): string {
  switch (status) {
    case "done":
      return "text-emerald-400";
    case "running":
    case "queued":
      return "text-amber-400";
    case "error":
    case "budget_exceeded":
      return "text-rose-400";
    default:
      return "text-neutral-500";
  }
}
