import type { PerformanceRow } from "../types.js";

interface Props {
  rows: PerformanceRow[];
}

export function PerformanceTable({ rows }: Props): JSX.Element {
  return (
    <div className="border border-neutral-800 rounded overflow-hidden">
      <header className="px-3 py-2 border-b border-neutral-800 text-xs text-neutral-400 uppercase tracking-wide">
        Performance
      </header>
      {rows.length === 0 ? (
        <div className="px-3 py-4 text-xs text-neutral-600">
          No performance rows yet. They populate once the Time Machine (Phase 5)
          starts scoring this persona.
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-xs text-neutral-500">
            <tr className="border-b border-neutral-800">
              <th className="text-left px-3 py-2">Period</th>
              <th className="text-right px-3 py-2">Trades</th>
              <th className="text-right px-3 py-2">Hit rate</th>
              <th className="text-right px-3 py-2">Avg return</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-neutral-900">
                <td className="px-3 py-2">{r.period}</td>
                <td className="text-right px-3 py-2">{r.trades}</td>
                <td className="text-right px-3 py-2">
                  {r.hit_rate !== null ? `${(r.hit_rate * 100).toFixed(1)}%` : "—"}
                </td>
                <td className="text-right px-3 py-2">
                  {r.avg_return !== null
                    ? `${(r.avg_return * 100).toFixed(2)}%`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
