import { useEffect } from "react";
import { useCommittee } from "../committeeStore.js";
import { CommitteeForm } from "../components/CommitteeForm.js";
import { AgentStream } from "../components/AgentStream.js";
import { TranscriptView } from "../components/TranscriptView.js";

// CLAUDE.md §6 order: moderator → personas → risk → pm.
const SPEAKERS: { agent: string; label: string }[] = [
  { agent: "moderator", label: "Moderator" },
  { agent: "buffett", label: "Buffett" },
  { agent: "druckenmiller", label: "Druckenmiller" },
  { agent: "burry", label: "Burry" },
  { agent: "risk", label: "Risk officer" },
  { agent: "pm", label: "PM" },
];

export function CommitteeRoom(): JSX.Element {
  const active = useCommittee((s) => s.active);
  const apply = useCommittee((s) => s.apply);

  useEffect(() => {
    return window.api.onJobEvent((jobId, event) => apply(jobId, event));
  }, [apply]);

  const graphStatus = active?.statusByAgent["graph"];

  return (
    <div className="flex flex-col gap-6 min-w-0">
      <section className="border border-neutral-800 rounded p-4 bg-neutral-950/60">
        <CommitteeForm />
      </section>

      {active && (
        <section className="flex flex-col gap-3">
          <div className="flex justify-between items-baseline text-xs text-neutral-500">
            <span className="font-mono">
              {active.ticker} · job {active.id.slice(0, 8)}
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

          <div className="grid grid-cols-2 gap-3">
            {SPEAKERS.map((s) => (
              <AgentStream
                key={s.agent}
                agent={s.agent}
                label={s.label}
                status={active.statusByAgent[s.agent]}
                tokens={active.tokensByAgent[s.agent] ?? ""}
              />
            ))}
          </div>

          {active.artifacts.map((a) => (
            <TranscriptView key={a.id ?? `${a.kind}-new`} artifact={a} />
          ))}
        </section>
      )}
    </div>
  );
}
