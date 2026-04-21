interface Props {
  agent: string;
  label: string;
  status: string | undefined;
  tokens: string;
}

export function AgentStream({ agent, label, status, tokens }: Props): JSX.Element {
  const empty = !tokens && !status;
  return (
    <div className="border border-neutral-800 rounded bg-neutral-900/60">
      <header className="flex justify-between items-baseline px-3 py-2 border-b border-neutral-800">
        <div className="text-sm font-medium text-neutral-200">
          {label}
          <span className="ml-2 text-xs text-neutral-500 font-mono">{agent}</span>
        </div>
        <span className={`text-xs ${statusColor(status)}`}>
          {status ?? "idle"}
        </span>
      </header>
      <div className="px-3 py-2 text-sm font-mono whitespace-pre-wrap min-h-[5rem] max-h-[14rem] overflow-y-auto text-neutral-100">
        {empty ? <span className="text-neutral-600">—</span> : tokens}
      </div>
    </div>
  );
}

function statusColor(status: string | undefined): string {
  switch (status) {
    case "done":
      return "text-emerald-400";
    case "thinking":
    case "running_analysts":
    case "fetching_market_data":
    case "synthesizing":
      return "text-amber-400";
    case "budget_exceeded":
    case "error":
      return "text-rose-400";
    default:
      return "text-neutral-500";
  }
}
