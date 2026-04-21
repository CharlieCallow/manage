import { useState } from "react";
import type { PersonaName } from "../types.js";
import { useResearch } from "../store.js";

const PERSONAS: { id: PersonaName; label: string; tagline: string }[] = [
  { id: "buffett", label: "Buffett", tagline: "moats, owner-earnings, decades" },
  { id: "druckenmiller", label: "Druckenmiller", tagline: "macro, flows, cycle" },
  { id: "burry", label: "Burry", tagline: "balance sheet, contrarian" },
];

export function ResearchForm(): JSX.Element {
  const [ticker, setTicker] = useState("NVDA");
  const [persona, setPersona] = useState<PersonaName>("buffett");
  const [prompt, setPrompt] = useState("");
  const running = useResearch((s) => s.active?.running ?? false);
  const start = useResearch((s) => s.start);

  function submit(e: React.FormEvent): void {
    e.preventDefault();
    void start({ persona, ticker, prompt: prompt.trim() || undefined });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="flex gap-3">
        <div className="flex-1">
          <label className="text-xs text-neutral-400 block mb-1">Ticker</label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="NVDA"
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 font-mono uppercase"
          />
        </div>
        <div className="flex-[2]">
          <label className="text-xs text-neutral-400 block mb-1">Persona</label>
          <div className="grid grid-cols-3 gap-2">
            {PERSONAS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setPersona(p.id)}
                className={`text-left px-3 py-2 rounded border text-sm ${
                  persona === p.id
                    ? "border-amber-500 bg-amber-500/10 text-amber-200"
                    : "border-neutral-800 bg-neutral-900 text-neutral-300 hover:border-neutral-700"
                }`}
              >
                <div className="font-medium">{p.label}</div>
                <div className="text-xs text-neutral-500">{p.tagline}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
      <div>
        <label className="text-xs text-neutral-400 block mb-1">
          Framing (optional)
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={2}
          placeholder="Any angle you want them to consider? Leave blank for a full workup."
          className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm"
        />
      </div>
      <div>
        <button
          type="submit"
          disabled={running || ticker.trim().length === 0}
          className="px-4 py-2 rounded bg-amber-500 text-neutral-950 text-sm font-medium disabled:opacity-40"
        >
          {running ? "Running…" : "Run research"}
        </button>
      </div>
    </form>
  );
}
