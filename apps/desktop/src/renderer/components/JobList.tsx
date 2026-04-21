import { useNav } from "../navStore.js";
import type { JobStatus, JobSummary } from "../types.js";

interface Props {
  jobs: JobSummary[];
  activeId: string | null;
}

export function JobList({ jobs, activeId }: Props): JSX.Element {
  const openJob = useNav((s) => s.openJob);
  if (jobs.length === 0) {
    return (
      <div className="text-xs text-neutral-600 px-3 py-2">
        No jobs yet. Submit one on the left.
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-1">
      {jobs.map((j) => (
        <li key={j.id}>
          <button
            type="button"
            onClick={() => openJob(j.id)}
            title="Open in Archive"
            className={`w-full text-left px-3 py-2 rounded border text-xs hover:border-neutral-700 ${
              activeId === j.id
                ? "border-amber-600 bg-amber-500/10"
                : "border-neutral-800 bg-neutral-900/60"
            }`}
          >
            <div className="flex justify-between items-baseline">
              <span className="font-mono font-medium text-neutral-200">
                {j.ticker ?? j.type}
              </span>
              <span className={statusColor(j.status)}>{j.status}</span>
            </div>
            <div className="flex justify-between text-neutral-500 mt-0.5">
              <span>{j.persona ?? j.type}</span>
              <span className="font-mono">${j.cost_usd.toFixed(4)}</span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

function statusColor(status: JobStatus): string {
  switch (status) {
    case "done":
      return "text-emerald-400";
    case "running":
    case "queued":
      return "text-amber-400";
    case "error":
    case "budget_exceeded":
      return "text-rose-400";
  }
}
