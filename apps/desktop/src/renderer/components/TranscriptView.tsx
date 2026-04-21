import ReactMarkdown from "react-markdown";
import type { ArtifactPayload } from "../types.js";

interface Props {
  artifact: ArtifactPayload;
}

export function TranscriptView({ artifact }: Props): JSX.Element {
  const md = artifact.content_md ?? "(transcript unavailable)";
  const meta = (artifact.content_json as Record<string, unknown> | null) ?? {};
  const verdict =
    typeof meta["verdict"] === "string" ? (meta["verdict"] as string) : null;

  return (
    <article className="border border-emerald-900 rounded bg-emerald-950/20 px-4 py-3">
      <header className="flex justify-between items-baseline mb-3">
        <h2 className="text-sm font-semibold text-emerald-300">Transcript</h2>
        {verdict && (
          <span className="font-mono text-xs px-2 py-1 rounded bg-emerald-900/60 text-emerald-100 uppercase tracking-wide">
            verdict: {verdict}
          </span>
        )}
      </header>
      <div className="prose prose-invert prose-sm max-w-none prose-headings:text-neutral-100 prose-p:text-neutral-200 prose-li:text-neutral-200 prose-strong:text-neutral-100">
        <ReactMarkdown>{md}</ReactMarkdown>
      </div>
    </article>
  );
}
