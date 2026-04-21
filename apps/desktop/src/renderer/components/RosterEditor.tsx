import { useEffect, useState } from "react";
import type { ModelId, RosterKind, RosterRow } from "../types.js";

const MODELS: { id: ModelId; label: string; cost: string }[] = [
  { id: "claude-haiku-4-5", label: "Haiku 4.5", cost: "$1 / $5 per 1M tok" },
  { id: "claude-sonnet-4-6", label: "Sonnet 4.6 (default)", cost: "$3 / $15" },
  { id: "claude-opus-4-7", label: "Opus 4.7", cost: "$15 / $75" },
];

interface Props {
  kind: RosterKind;
  row: RosterRow;
  onSaved(row: RosterRow): void;
}

export function RosterEditor({ kind, row, onSaved }: Props): JSX.Element {
  const [prompt, setPrompt] = useState(row.prompt_template);
  const [model, setModel] = useState<ModelId>(row.model);
  const [enabled, setEnabled] = useState(row.enabled);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPrompt(row.prompt_template);
    setModel(row.model);
    setEnabled(row.enabled);
    setError(null);
  }, [row.id, row.prompt_template, row.model, row.enabled]);

  const dirty =
    prompt !== row.prompt_template ||
    model !== row.model ||
    enabled !== row.enabled;

  async function save(): Promise<void> {
    setSaving(true);
    setError(null);
    try {
      const body: { prompt_template?: string; model?: ModelId; enabled?: boolean } =
        {};
      if (prompt !== row.prompt_template) body.prompt_template = prompt;
      if (model !== row.model) body.model = model;
      if (enabled !== row.enabled) body.enabled = enabled;
      const saved = await window.api.updateRosterMember(kind, row.name, body);
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-semibold capitalize">{row.name}</h3>
        <div className="text-xs text-neutral-500 font-mono">
          id #{row.id} · created {row.created_at.slice(0, 10)}
        </div>
      </div>

      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 items-center">
        <label className="text-xs text-neutral-400" htmlFor={`model-${row.id}`}>
          Model
        </label>
        <select
          id={`model-${row.id}`}
          value={model}
          onChange={(e) => setModel(e.target.value as ModelId)}
          className="bg-neutral-900 border border-neutral-800 rounded px-2 py-1.5 text-sm"
        >
          {MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label} — {m.cost}
            </option>
          ))}
        </select>

        <label className="text-xs text-neutral-400" htmlFor={`enabled-${row.id}`}>
          Enabled
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            id={`enabled-${row.id}`}
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          <span className="text-neutral-400">
            Disabled {kind === "personas" ? "personas" : "analysts"} can't be
            picked for new jobs.
          </span>
        </label>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-neutral-400" htmlFor={`prompt-${row.id}`}>
          Prompt template (system prompt)
        </label>
        <textarea
          id={`prompt-${row.id}`}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={16}
          className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 font-mono text-xs leading-relaxed"
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => void save()}
          disabled={!dirty || saving}
          className="px-4 py-2 rounded bg-amber-500 text-neutral-950 text-sm font-medium disabled:opacity-40"
        >
          {saving ? "Saving…" : dirty ? "Save changes" : "Saved"}
        </button>
        {error && <span className="text-rose-400 text-xs">{error}</span>}
      </div>
    </div>
  );
}
