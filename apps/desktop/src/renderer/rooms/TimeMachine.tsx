import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { BacktestForm } from "../components/BacktestForm.js";
import {
  ScoreboardTable,
  type ScoreboardRow,
} from "../components/ScoreboardTable.js";
import { useBacktest } from "../backtestStore.js";
import type { PersonaName } from "../types.js";

const PERSONAS: PersonaName[] = ["buffett", "druckenmiller", "burry"];

export function TimeMachine(): JSX.Element {
  const active = useBacktest((s) => s.active);
  const apply = useBacktest((s) => s.apply);

  const [scoreboard, setScoreboard] = useState<ScoreboardRow[]>([]);

  useEffect(() => {
    return window.api.onJobEvent((jobId, event) => apply(jobId, event));
  }, [apply]);

  const loadScoreboard = useCallback(async () => {
    const rows: ScoreboardRow[] = [];
    for (const p of PERSONAS) {
      try {
        const perf = await window.api.listPerformance(p);
        for (const r of perf) {
          rows.push({
            persona: p,
            period: r.period,
            trades: r.trades,
            hit_rate: r.hit_rate,
            avg_return: r.avg_return,
          });
        }
      } catch {
        // non-fatal; skip
      }
    }
    setScoreboard(rows);
  }, []);

  useEffect(() => {
    void loadScoreboard();
  }, [loadScoreboard]);

  // Refresh the scoreboard when a backtest finishes.
  useEffect(() => {
    if (active && !active.running) void loadScoreboard();
  }, [active, loadScoreboard]);

  return (
    <div className="flex flex-col gap-6 min-w-0">
      <section className="border border-neutral-800 rounded p-4 bg-neutral-950/60">
        <BacktestForm />
      </section>

      {active && (
        <section className="flex flex-col gap-3">
          <div className="flex justify-between items-baseline text-xs text-neutral-500">
            <span className="font-mono">
              {active.ticker} · {active.persona} · job {active.id.slice(0, 8)}
            </span>
            <span>
              {active.costUsd !== null && <>cost ${active.costUsd.toFixed(4)}</>}
              <span className="ml-3">status: {active.status}</span>
            </span>
          </div>
          {active.error && (
            <div className="text-rose-400 text-sm border border-rose-900 rounded px-3 py-2">
              {active.error}
            </div>
          )}

          <div className="border border-neutral-800 rounded bg-neutral-900/60 p-3">
            <header className="text-xs text-neutral-400 uppercase tracking-wide mb-2">
              Run log
            </header>
            <pre className="text-xs font-mono whitespace-pre-wrap text-neutral-200 min-h-[6rem] max-h-[20rem] overflow-y-auto">
              {active.log || (
                <span className="text-neutral-600">
                  Waiting for the first step…
                </span>
              )}
            </pre>
          </div>

          {active.artifacts.map((a) => (
            <article
              key={a.id ?? `${a.kind}-new`}
              className="border border-emerald-900 rounded bg-emerald-950/20 px-4 py-3"
            >
              <header className="flex justify-between items-baseline mb-2">
                <h2 className="text-sm font-semibold text-emerald-300">
                  Backtest report
                </h2>
              </header>
              <div className="prose prose-invert prose-sm max-w-none prose-headings:text-neutral-100 prose-p:text-neutral-200 prose-li:text-neutral-200 prose-strong:text-neutral-100 prose-table:text-xs">
                <ReactMarkdown>{a.content_md ?? ""}</ReactMarkdown>
              </div>
            </article>
          ))}
        </section>
      )}

      <ScoreboardTable rows={scoreboard} />
    </div>
  );
}
