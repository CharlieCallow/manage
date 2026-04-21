import { useState } from "react";
import type { Idea } from "../types.js";

interface Props {
  idea: Idea;
  onDecided(ideaId: number, researchJobId: string | null): void;
}

export function IdeaCard({ idea, onDecided }: Props): JSX.Element {
  const [busy, setBusy] = useState<"approve" | "dismiss" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(status: "approved" | "dismissed"): Promise<void> {
    setBusy(status === "approved" ? "approve" : "dismiss");
    setError(null);
    try {
      const res = await window.api.decideIdea(idea.id, { status });
      onDecided(idea.id, res.research_job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="border border-neutral-800 rounded bg-neutral-950/60 p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="font-mono font-semibold text-neutral-100 text-lg">
            {idea.ticker}
          </div>
          <div className="text-xs text-neutral-500 capitalize">
            {idea.persona}
          </div>
        </div>
        <div className="text-xs text-neutral-600 font-mono">
          #{idea.id}
        </div>
      </div>
      <p className="text-sm text-neutral-200 leading-relaxed">{idea.thesis}</p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void decide("approved")}
          disabled={busy !== null}
          className="flex-1 px-3 py-1.5 rounded bg-emerald-600 text-emerald-50 text-sm font-medium disabled:opacity-40 hover:bg-emerald-500"
        >
          {busy === "approve" ? "Approving…" : "Approve → research"}
        </button>
        <button
          type="button"
          onClick={() => void decide("dismissed")}
          disabled={busy !== null}
          className="px-3 py-1.5 rounded bg-neutral-800 text-neutral-300 text-sm disabled:opacity-40 hover:bg-neutral-700"
        >
          {busy === "dismiss" ? "…" : "Dismiss"}
        </button>
      </div>
      {error && <div className="text-xs text-rose-400">{error}</div>}
    </div>
  );
}
