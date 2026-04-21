import { useState } from "react";
import type { PersonaName } from "../types.js";
import { useBacktest } from "../backtestStore.js";

const PERSONAS: { id: PersonaName; label: string }[] = [
  { id: "buffett", label: "Buffett" },
  { id: "druckenmiller", label: "Druckenmiller" },
  { id: "burry", label: "Burry" },
];

function defaultStart(): string {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 1);
  return d.toISOString().slice(0, 10);
}

export function BacktestForm(): JSX.Element {
  const [persona, setPersona] = useState<PersonaName>("buffett");
  const [ticker, setTicker] = useState("NVDA");
  const [startDate, setStartDate] = useState(defaultStart());
  const [numSteps, setNumSteps] = useState(12);
  const [stepWeeks, setStepWeeks] = useState(1);
  const running = useBacktest((s) => s.active?.running ?? false);
  const start = useBacktest((s) => s.start);

  function submit(e: React.FormEvent): void {
    e.preventDefault();
    void start({ persona, ticker, startDate, numSteps, stepWeeks, budgetUsd: 1.0 });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="flex gap-3 items-end">
        <div className="w-40">
          <label className="text-xs text-neutral-400 block mb-1">Ticker</label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="NVDA"
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 font-mono uppercase"
          />
        </div>
        <div className="w-48">
          <label className="text-xs text-neutral-400 block mb-1">Persona</label>
          <select
            value={persona}
            onChange={(e) => setPersona(e.target.value as PersonaName)}
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm capitalize"
          >
            {PERSONAS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
        <div className="w-44">
          <label className="text-xs text-neutral-400 block mb-1">Start date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 font-mono text-sm"
          />
        </div>
        <div className="w-24">
          <label className="text-xs text-neutral-400 block mb-1">Steps</label>
          <input
            type="number"
            min={1}
            max={52}
            value={numSteps}
            onChange={(e) => setNumSteps(parseInt(e.target.value || "0", 10))}
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 font-mono text-sm"
          />
        </div>
        <div className="w-28">
          <label className="text-xs text-neutral-400 block mb-1">Weeks/step</label>
          <input
            type="number"
            min={1}
            max={8}
            value={stepWeeks}
            onChange={(e) => setStepWeeks(parseInt(e.target.value || "1", 10))}
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 font-mono text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={running || ticker.trim().length === 0}
          className="px-4 py-2 rounded bg-amber-500 text-neutral-950 text-sm font-medium disabled:opacity-40"
        >
          {running ? "Running…" : "Run backtest"}
        </button>
      </div>
      <div className="text-xs text-neutral-500">
        Scorer runs on Haiku per §8. Default budget is $1.00 (typical 12-step run
        is under $0.05).
      </div>
    </form>
  );
}
