import { useEffect, useState } from "react";
import { useDebugPanel } from "./store.js";

export function App(): JSX.Element {
  const [prompt, setPrompt] = useState("What do you think about KO today?");
  const { jobId, tokens, status, error, costUsd, running, start, reset, apply } =
    useDebugPanel();

  useEffect(() => {
    return window.api.onJobEvent((_jobId, event) => apply(event));
  }, [apply]);

  return (
    <div className="min-h-screen p-6 flex flex-col gap-4 max-w-3xl mx-auto">
      <header className="flex items-baseline justify-between">
        <h1 className="text-xl font-semibold">manage · debug panel</h1>
        <span className="text-xs text-neutral-500">Phase 0 · Buffett</span>
      </header>

      <section className="flex flex-col gap-2">
        <label htmlFor="prompt" className="text-sm text-neutral-400">
          Ask Buffett
        </label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          className="bg-neutral-900 border border-neutral-800 rounded p-3 font-mono text-sm focus:outline-none focus:border-neutral-600"
        />
        <div className="flex gap-2">
          <button
            onClick={() => void start(prompt)}
            disabled={running || prompt.trim().length === 0}
            className="px-3 py-1.5 rounded bg-amber-500 text-neutral-950 text-sm font-medium disabled:opacity-40"
          >
            {running ? "Running…" : "Run"}
          </button>
          <button
            onClick={reset}
            disabled={running}
            className="px-3 py-1.5 rounded bg-neutral-800 text-neutral-200 text-sm disabled:opacity-40"
          >
            Reset
          </button>
        </div>
      </section>

      <section className="flex flex-col gap-1 text-xs text-neutral-500">
        <div>job: {jobId ?? "—"}</div>
        <div>status: {status || "idle"}</div>
        {costUsd !== null && <div>cost: ${costUsd.toFixed(4)}</div>}
        {error && <div className="text-rose-400">error: {error}</div>}
      </section>

      <section className="flex-1 bg-neutral-900 border border-neutral-800 rounded p-4 whitespace-pre-wrap font-mono text-sm min-h-[12rem]">
        {tokens || (
          <span className="text-neutral-600">
            Stream from a hard-coded Buffett persona will render here.
          </span>
        )}
      </section>
    </div>
  );
}
