import { useState } from "react";
import { useCommittee } from "../committeeStore.js";

export function CommitteeForm(): JSX.Element {
  const [ticker, setTicker] = useState("NVDA");
  const [prompt, setPrompt] = useState("");
  const running = useCommittee((s) => s.active?.running ?? false);
  const start = useCommittee((s) => s.start);

  function submit(e: React.FormEvent): void {
    e.preventDefault();
    // Committee runs 6 speakers; lift the default job budget so it can finish.
    void start({ ticker, prompt: prompt.trim() || undefined, budgetUsd: 1.0 });
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
        <div className="flex-1">
          <label className="text-xs text-neutral-400 block mb-1">
            Framing for the moderator (optional)
          </label>
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Any angle you want the committee to focus on?"
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={running || ticker.trim().length === 0}
          className="px-4 py-2 rounded bg-amber-500 text-neutral-950 text-sm font-medium disabled:opacity-40"
        >
          {running ? "In session…" : "Convene committee"}
        </button>
      </div>
      <div className="text-xs text-neutral-500">
        Committee runs six speakers in order: moderator · buffett · druckenmiller
        · burry · risk · pm. Budget for this job is capped at $1.00.
      </div>
    </form>
  );
}
