import { useState } from "react";
import { useIdeation } from "../ideationStore.js";

export function IdeationForm(): JSX.Element {
  const [framing, setFraming] = useState("");
  const [numPerPersona, setNum] = useState(3);
  const running = useIdeation((s) => s.active?.running ?? false);
  const start = useIdeation((s) => s.start);

  function submit(e: React.FormEvent): void {
    e.preventDefault();
    void start({
      framing: framing.trim() || undefined,
      numPerPersona,
      budgetUsd: 1.0,
    });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="flex gap-3 items-end">
        <div className="flex-1">
          <label className="text-xs text-neutral-400 block mb-1">
            Theme or framing (optional)
          </label>
          <input
            value={framing}
            onChange={(e) => setFraming(e.target.value)}
            placeholder="e.g. AI infrastructure, GLP-1 winners, or leave blank"
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm"
          />
        </div>
        <div className="w-36">
          <label className="text-xs text-neutral-400 block mb-1">
            Ideas per persona
          </label>
          <input
            type="number"
            min={1}
            max={6}
            value={numPerPersona}
            onChange={(e) => setNum(parseInt(e.target.value || "1", 10))}
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 font-mono text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={running}
          className="px-4 py-2 rounded bg-amber-500 text-neutral-950 text-sm font-medium disabled:opacity-40"
        >
          {running ? "Thinking…" : "Surface ideas"}
        </button>
      </div>
      <div className="text-xs text-neutral-500">
        Every enabled persona surfaces candidates in parallel. Approving a
        candidate kicks off a full Research Desk job using its thesis as
        framing.
      </div>
    </form>
  );
}
