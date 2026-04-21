import { useEffect } from "react";
import { AgentStream } from "../components/AgentStream.js";
import { IdeaCard } from "../components/IdeaCard.js";
import { IdeationForm } from "../components/IdeationForm.js";
import { useIdeation } from "../ideationStore.js";
import { useNav } from "../navStore.js";
import type { Idea, PersonaName } from "../types.js";

const PERSONAS: { id: PersonaName; label: string }[] = [
  { id: "buffett", label: "Buffett" },
  { id: "druckenmiller", label: "Druckenmiller" },
  { id: "burry", label: "Burry" },
];

export function Ideas(): JSX.Element {
  const active = useIdeation((s) => s.active);
  const pending = useIdeation((s) => s.pending);
  const history = useIdeation((s) => s.history);
  const apply = useIdeation((s) => s.apply);
  const refresh = useIdeation((s) => s.refresh);
  const afterDecision = useIdeation((s) => s.afterDecision);
  const openJob = useNav((s) => s.openJob);

  useEffect(() => {
    void refresh();
    return window.api.onJobEvent((jobId, event) => apply(jobId, event));
  }, [apply, refresh]);

  const graphStatus = active?.statusByAgent["graph"];
  const byPersona = groupBy(pending, (i) => i.persona);

  return (
    <div className="flex flex-col gap-6 min-w-0">
      <section className="border border-neutral-800 rounded p-4 bg-neutral-950/60">
        <IdeationForm />
      </section>

      {active && (
        <section className="flex flex-col gap-3">
          <div className="flex justify-between items-baseline text-xs text-neutral-500">
            <span className="font-mono">
              {active.framing ? `"${active.framing}"` : "(no framing)"} · job{" "}
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
          <div className="grid grid-cols-3 gap-3">
            {PERSONAS.map((p) => (
              <AgentStream
                key={p.id}
                agent={p.id}
                label={p.label}
                status={active.statusByAgent[p.id]}
                tokens={active.tokensByAgent[p.id] ?? ""}
              />
            ))}
          </div>
        </section>
      )}

      <section>
        <header className="flex justify-between items-baseline mb-3">
          <h2 className="text-sm font-semibold text-neutral-200">
            Pending ideas
          </h2>
          <span className="text-xs text-neutral-500">
            {pending.length} awaiting your call
          </span>
        </header>
        {pending.length === 0 ? (
          <div className="text-xs text-neutral-600 px-3 py-4 border border-neutral-800 rounded bg-neutral-950/60">
            No pending ideas. Run "Surface ideas" above to get candidates.
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {PERSONAS.map((p) => {
              const rows = byPersona[p.id] ?? [];
              if (rows.length === 0) return null;
              return (
                <div key={p.id}>
                  <h3 className="text-xs text-neutral-400 uppercase tracking-wide mb-2">
                    {p.label}
                  </h3>
                  <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    {rows.map((idea) => (
                      <IdeaCard
                        key={idea.id}
                        idea={idea}
                        onDecided={afterDecision}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {history.length > 0 && (
        <section>
          <header className="flex justify-between items-baseline mb-3">
            <h2 className="text-sm font-semibold text-neutral-200">
              Decided history
            </h2>
            <span className="text-xs text-neutral-500">
              {history.length} total
            </span>
          </header>
          <ul className="flex flex-col gap-1">
            {history.map((idea) => (
              <HistoryRow
                key={idea.id}
                idea={idea}
                onOpen={(jobId) => openJob(jobId)}
              />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function HistoryRow({
  idea,
  onOpen,
}: {
  idea: Idea;
  onOpen(jobId: string): void;
}): JSX.Element {
  const approved = idea.status === "approved";
  return (
    <li className="flex items-baseline gap-3 text-sm border border-neutral-900 rounded bg-neutral-950/60 px-3 py-2">
      <span className="font-mono font-semibold text-neutral-100 w-16">
        {idea.ticker}
      </span>
      <span className="text-xs text-neutral-500 w-28 capitalize">
        {idea.persona}
      </span>
      <span className="text-neutral-300 flex-1 truncate" title={idea.thesis}>
        {idea.thesis}
      </span>
      <span
        className={`text-xs font-mono ${
          approved ? "text-emerald-400" : "text-neutral-500"
        }`}
      >
        {idea.status}
      </span>
      {approved && idea.research_job_id && (
        <button
          type="button"
          onClick={() => onOpen(idea.research_job_id as string)}
          className="text-xs px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200"
        >
          open report →
        </button>
      )}
    </li>
  );
}

function groupBy<T, K extends string>(
  rows: T[],
  key: (row: T) => K,
): Record<K, T[]> {
  const out = {} as Record<K, T[]>;
  for (const row of rows) {
    const k = key(row);
    if (!out[k]) out[k] = [];
    out[k].push(row);
  }
  return out;
}
