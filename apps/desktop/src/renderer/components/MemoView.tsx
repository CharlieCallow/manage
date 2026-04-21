import ReactMarkdown from "react-markdown";
import type { ArtifactPayload } from "../types.js";

interface Props {
  artifact: ArtifactPayload;
}

export function MemoView({ artifact }: Props): JSX.Element {
  const md = artifact.content_md ?? "(memo unavailable)";
  return (
    <article className="border border-emerald-900 rounded bg-emerald-950/20 px-4 py-3">
      <header className="flex justify-between items-baseline mb-2">
        <h2 className="text-sm font-semibold text-emerald-300">Memo</h2>
        <span className="text-xs text-neutral-500 font-mono">
          artifact #{artifact.id ?? "—"}
        </span>
      </header>
      <div className="prose prose-invert prose-sm max-w-none prose-headings:text-neutral-100 prose-p:text-neutral-200 prose-li:text-neutral-200 prose-strong:text-neutral-100">
        <ReactMarkdown>{md}</ReactMarkdown>
      </div>
    </article>
  );
}
