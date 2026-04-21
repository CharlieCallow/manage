import { useEffect } from "react";
import { useResearch } from "./store.js";
import { ResearchForm } from "./components/ResearchForm.js";
import { AgentStream } from "./components/AgentStream.js";
import { MemoView } from "./components/MemoView.js";
import { JobList } from "./components/JobList.js";

const ANALYSTS: { agent: string; label: string }[] = [
  { agent: "valuation", label: "Valuation analyst" },
  { agent: "fundamentals", label: "Fundamentals analyst" },
];

export function App(): JSX.Element {
  const active = useResearch((s) => s.active);
  const jobs = useResearch((s) => s.jobs);
  const apply = useResearch((s) => s.apply);
  const loadJobs = useResearch((s) => s.loadJobs);

  useEffect(() => {
    void loadJobs();
    return window.api.onJobEvent((jobId, event) => apply(jobId, event));
  }, [apply, loadJobs]);

  const graphStatus = active?.statusByAgent["graph"];
  const personaAgent = active?.persona ?? "buffett";
  const personaLabel =
    personaAgent.charAt(0).toUpperCase() + personaAgent.slice(1);

  return (
    <div className="min-h-screen grid grid-cols-[1fr_20rem] gap-6 p-6 max-w-[120rem] mx-auto">
      <main className="flex flex-col gap-6 min-w-0">
        <header className="flex items-baseline justify-between">
          <h1 className="text-xl font-semibold">manage · Research Desk</h1>
          <span className="text-xs text-neutral-500">Phase 1</span>
        </header>

        <section className="border border-neutral-800 rounded p-4 bg-neutral-950/60">
          <ResearchForm />
        </section>

        {active && (
          <section className="flex flex-col gap-3">
            <div className="flex justify-between items-baseline text-xs text-neutral-500">
              <span className="font-mono">
                {active.ticker} · {active.persona} · job {active.id.slice(0, 8)}
              </span>
              <span>
                {active.costUsd !== null && <>cost ${active.costUsd.toFixed(4)}</>}{" "}
                {graphStatus && <span className="ml-3">graph: {graphStatus}</span>}
              </span>
            </div>
            {active.error && (
              <div className="text-rose-400 text-sm border border-rose-900 rounded px-3 py-2">
                {active.error}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              {ANALYSTS.map((a) => (
                <AgentStream
                  key={a.agent}
                  agent={a.agent}
                  label={a.label}
                  status={active.statusByAgent[a.agent]}
                  tokens={active.tokensByAgent[a.agent] ?? ""}
                />
              ))}
            </div>

            <AgentStream
              agent={personaAgent}
              label={`${personaLabel} (synthesis)`}
              status={active.statusByAgent[personaAgent]}
              tokens={active.tokensByAgent[personaAgent] ?? ""}
            />

            {active.artifacts.map((a) => (
              <MemoView key={a.id ?? `${a.kind}-new`} artifact={a} />
            ))}
          </section>
        )}
      </main>

      <aside className="flex flex-col gap-3 min-w-0">
        <h2 className="text-xs text-neutral-400 uppercase tracking-wide">
          Recent jobs
        </h2>
        <JobList jobs={jobs} activeId={active?.id ?? null} />
      </aside>
    </div>
  );
}
