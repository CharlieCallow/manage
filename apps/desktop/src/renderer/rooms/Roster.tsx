import { useCallback, useEffect, useState } from "react";
import { RosterEditor } from "../components/RosterEditor.js";
import { PerformanceTable } from "../components/PerformanceTable.js";
import type { PerformanceRow, RosterKind, RosterRow } from "../types.js";

export function Roster(): JSX.Element {
  const [kind, setKind] = useState<RosterKind>("personas");
  const [rows, setRows] = useState<RosterRow[]>([]);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [performance, setPerformance] = useState<PerformanceRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (k: RosterKind): Promise<void> => {
      setLoading(true);
      setError(null);
      try {
        const list = await window.api.listRoster(k);
        setRows(list);
        setSelectedName((prev) => {
          if (prev && list.some((r) => r.name === prev)) return prev;
          return list[0]?.name ?? null;
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void load(kind);
  }, [kind, load]);

  const selected = rows.find((r) => r.name === selectedName) ?? null;

  useEffect(() => {
    if (kind !== "personas" || !selected) {
      setPerformance([]);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const perf = await window.api.listPerformance(selected.name);
        if (!cancelled) setPerformance(perf);
      } catch {
        if (!cancelled) setPerformance([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [kind, selected]);

  function handleSaved(saved: RosterRow): void {
    setRows((prev) => prev.map((r) => (r.id === saved.id ? saved : r)));
  }

  return (
    <div className="grid grid-cols-[14rem_1fr] gap-6 min-w-0">
      <aside className="flex flex-col gap-2">
        <div className="flex gap-1 bg-neutral-900 rounded p-1 border border-neutral-800">
          {(["personas", "analysts"] as const).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              className={`flex-1 px-2 py-1 rounded text-xs capitalize ${
                kind === k
                  ? "bg-neutral-800 text-neutral-100"
                  : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              {k}
            </button>
          ))}
        </div>
        {loading && (
          <div className="text-xs text-neutral-600 px-2">loading…</div>
        )}
        {error && (
          <div className="text-xs text-rose-400 px-2">{error}</div>
        )}
        <ul className="flex flex-col gap-1">
          {rows.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => setSelectedName(r.name)}
                className={`w-full text-left px-3 py-2 rounded text-sm capitalize border ${
                  selectedName === r.name
                    ? "border-amber-600 bg-amber-500/10 text-amber-200"
                    : "border-neutral-800 bg-neutral-900/60 text-neutral-200 hover:border-neutral-700"
                }`}
              >
                <div className="flex justify-between items-baseline">
                  <span>{r.name}</span>
                  {!r.enabled && (
                    <span className="text-xs text-neutral-500">off</span>
                  )}
                </div>
                <div className="text-xs text-neutral-500 font-mono">
                  {r.model}
                </div>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="flex flex-col gap-6 min-w-0">
        {selected ? (
          <>
            <section className="border border-neutral-800 rounded p-4 bg-neutral-950/60">
              <RosterEditor kind={kind} row={selected} onSaved={handleSaved} />
            </section>
            {kind === "personas" && <PerformanceTable rows={performance} />}
          </>
        ) : (
          <div className="text-sm text-neutral-500">
            Select a {kind === "personas" ? "persona" : "analyst"}.
          </div>
        )}
      </main>
    </div>
  );
}
