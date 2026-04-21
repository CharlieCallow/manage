import type { DailySpend } from "../types.js";

interface Props {
  spend: DailySpend | null;
}

export function SpendWidget({ spend }: Props): JSX.Element {
  if (!spend) {
    return (
      <div className="border border-neutral-800 rounded p-4 bg-neutral-950/60">
        <div className="text-xs text-neutral-500">loading spend…</div>
      </div>
    );
  }
  const pct = spend.daily_cap_usd
    ? Math.min(100, (spend.total_usd / spend.daily_cap_usd) * 100)
    : 0;
  const over = pct >= 100;
  return (
    <div className="border border-neutral-800 rounded p-4 bg-neutral-950/60 flex flex-col gap-3">
      <div className="flex justify-between items-baseline">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">
            Today's spend
          </h3>
          <div className="text-xs text-neutral-500">
            resets at UTC midnight
          </div>
        </div>
        <div className="text-right font-mono text-sm">
          <div className="text-neutral-100">
            ${spend.total_usd.toFixed(4)}{" "}
            <span className="text-neutral-500">
              / ${spend.daily_cap_usd.toFixed(2)}
            </span>
          </div>
          <div className="text-xs text-neutral-500">
            {spend.input_tokens + spend.output_tokens} tokens
          </div>
        </div>
      </div>

      <div className="h-2 rounded bg-neutral-900 overflow-hidden">
        <div
          className={`h-full ${over ? "bg-rose-500" : "bg-amber-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {spend.by_model.length > 0 && (
        <table className="w-full text-xs">
          <thead className="text-neutral-500">
            <tr>
              <th className="text-left pb-1">Model</th>
              <th className="text-right pb-1">Calls</th>
              <th className="text-right pb-1">Tokens (in/out)</th>
              <th className="text-right pb-1">Cost</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {spend.by_model.map((m) => (
              <tr key={m.model} className="border-t border-neutral-900">
                <td className="py-1 pr-2">{m.model}</td>
                <td className="text-right">{m.calls}</td>
                <td className="text-right text-neutral-400">
                  {m.input_tokens} / {m.output_tokens}
                </td>
                <td className="text-right text-neutral-100">
                  ${m.cost.toFixed(4)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
