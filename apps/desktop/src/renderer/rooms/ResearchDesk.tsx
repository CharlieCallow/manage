import { useEffect } from "react";
import { useResearch } from "../store.js";
import { ResearchForm } from "../components/ResearchForm.js";
import { AgentStream } from "../components/AgentStream.js";
import { MemoView } from "../components/MemoView.js";
import { JobList } from "../components/JobList.js";
import type { PersonaName } from "../types.js";

const ANALYSTS: { agent: string; label: string }[] = [
  { agent: "valuation", label: "Valuation" },
  { agent: "fundamentals", label: "Fundamentals" },
  { agent: "macro", label: "Macro" },
  { agent: "technicals", label: "Technicals" },
];

const ALL_PERSONAS: { id: PersonaName; label: string }[] = [
  { id: "buffett", label: "Buffett" },
  { id: "druckenmiller", label: "Druckenmiller" },
  { id: "burry", label: "Burry" },
];

export function ResearchDesk(): JSX.Element {
  const active = useResearch((s) => s.active);
  const jobs = useResearch((s) => s.jobs);
  const apply = useResearch((s) => s.apply);
  const loadJobs = useResearch((s) => s.loadJobs);

  useEffect(() => {
    void loadJobs();
    return window.api.onJobEvent((jobId, event) => apply(jobId, event));
  }, [apply, loadJobs]);

  const graphStatus = active?.statusByAgent["graph"];
  const leadAgent = active?.persona ?? "buffett";
  const leadLabel = leadAgent.charAt(0).toUpperCase() + leadAgent.slice(1);
  const contributors = ALL_PERSONAS.filter((p) => p.id !== leadAgent);

  return (
    <div className="grid grid-cols-[1fr_20rem] gap-6 min-w-0">
      <main className="flex flex-col gap-6 min-w-0">
        <section className="border border-neutral-800 rounded p-4 bg-neutral-950/60">
          <ResearchForm />
        </section>

        {active && (
          <section className="flex flex-col gap-3">
            <div className="flex justify-between items-baseline text-xs text-neutral-500">
              <span className="font-mono">
                {active.ticker} · lead: {active.persona} · job{" "}
                {active.id.slice(0, 8)}
              </span>
              <span>
                {active.costUsd !== null && <>cost ${active.costUsd.toFixed(4)}</>}
                {graphStatus && <span className="ml-3">graph: {graphStatus}</span>}
              </span>
            </div>
            {active.error && (
              <div className="text-rose-400 text-sm border border-rose-900 rounded px-3 py-2">
                {active.error}
              </div>
            )}

            <h3 className="text-xs text-neutral-400 uppercase tracking-wide">
              Analyst desk
            </h3>
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

            <h3 className="text-xs text-neutral-400 uppercase tracking-wide mt-3">
              Team views
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {contributors.map((p) => (
                <AgentStream
                  key={p.id}
                  agent={p.id}
                  label={`${p.label} (quick take)`}
                  status={active.statusByAgent[p.id]}
                  tokens={active.tokensByAgent[p.id] ?? ""}
                />
              ))}
            </div>

            <h3 className="text-xs text-neutral-400 uppercase tracking-wide mt-3">
              Lead synthesis
            </h3>
            <AgentStream
              agent={leadAgent}
              label={`${leadLabel} (lead author)`}
              status={active.statusByAgent[leadAgent]}
              tokens={active.tokensByAgent[leadAgent] ?? ""}
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
