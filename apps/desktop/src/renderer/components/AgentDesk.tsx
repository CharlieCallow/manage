import type { AgentActivity } from "../liveStore.js";
import type { RosterRow } from "../types.js";

interface Props {
  row: RosterRow;
  role: "persona" | "analyst";
  activity: AgentActivity | undefined;
}

export function AgentDesk({ row, role, activity }: Props): JSX.Element {
  const active = activity?.active ?? false;
  const status = activity?.status ?? "idle";
  const tail = activity?.lastText ?? "";

  const dot = active
    ? "bg-emerald-400 animate-pulse"
    : status === "done"
      ? "bg-emerald-700"
      : "bg-neutral-700";
  const border = active
    ? "border-emerald-700"
    : status === "budget_exceeded" || status === "error"
      ? "border-rose-900"
      : "border-neutral-800";

  return (
    <div
      className={`border ${border} rounded bg-neutral-950/60 p-3 flex flex-col gap-2 h-40 overflow-hidden`}
    >
      <header className="flex justify-between items-center">
        <div className="flex items-center gap-2 min-w-0">
          <span
            aria-hidden
            className={`inline-block w-2 h-2 rounded-full ${dot}`}
          />
          <span className="capitalize text-sm font-medium text-neutral-100 truncate">
            {row.name}
          </span>
          <span className="text-xs text-neutral-500 uppercase tracking-wide">
            {role}
          </span>
        </div>
        <span className="text-xs text-neutral-500 font-mono">{status}</span>
      </header>
      <div className="text-xs text-neutral-500 font-mono truncate">
        {row.model}
      </div>
      <div className="text-xs text-neutral-400 flex-1 overflow-hidden font-mono whitespace-pre-wrap leading-snug">
        {tail || <span className="text-neutral-700">—</span>}
      </div>
    </div>
  );
}
