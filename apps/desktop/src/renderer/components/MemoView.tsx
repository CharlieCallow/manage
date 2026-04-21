import ReactMarkdown from "react-markdown";
import type { ArtifactPayload } from "../types.js";

interface Props {
  artifact: ArtifactPayload;
}

interface MemoMeta {
  rating?: string | null;
  style?: string | null;
  ticker?: string | null;
  persona?: string | null;
  targets?: {
    base?: number | null;
    bull?: number | null;
    bear?: number | null;
  } | null;
}

const RATING_COLORS: Record<string, string> = {
  BUY: "bg-emerald-700 text-emerald-50",
  OVERWEIGHT: "bg-emerald-800 text-emerald-100",
  HOLD: "bg-neutral-700 text-neutral-100",
  NEUTRAL: "bg-neutral-700 text-neutral-100",
  UNDERWEIGHT: "bg-rose-900 text-rose-100",
  SELL: "bg-rose-700 text-rose-50",
};

function formatPrice(x: number | null | undefined): string {
  if (x == null) return "—";
  return `$${x.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function MemoView({ artifact }: Props): JSX.Element {
  const md = artifact.content_md ?? "(memo unavailable)";
  const meta = (artifact.content_json ?? {}) as MemoMeta;
  const rating = (meta.rating ?? "").toUpperCase();
  const ratingClass = RATING_COLORS[rating] ?? "bg-neutral-800 text-neutral-200";
  const targets = meta.targets ?? {};

  // Strip the header fields from the body since the banner renders them.
  const body = md.replace(
    /^\s*\*\*(Rating|Base target|Bull target|Bear target|Horizon):\*\*[^\n]*\n/gm,
    "",
  );

  return (
    <article className="border border-emerald-900 rounded bg-emerald-950/20">
      <header className="flex flex-wrap items-center gap-4 px-4 py-3 border-b border-emerald-900">
        <div className="flex flex-col">
          <span className="text-xs text-neutral-500 uppercase tracking-wide">
            Memo{meta.style ? ` · ${meta.style}` : ""}
          </span>
          <span className="text-sm font-semibold text-emerald-300">
            artifact #{artifact.id ?? "—"}
          </span>
        </div>
        {rating && (
          <span
            className={`px-3 py-1 rounded font-semibold text-xs tracking-wider ${ratingClass}`}
          >
            {rating}
          </span>
        )}
        <div className="flex gap-4 ml-auto text-xs font-mono">
          <Target label="Bear" value={targets.bear} tone="text-rose-300" />
          <Target label="Base" value={targets.base} tone="text-neutral-100" />
          <Target label="Bull" value={targets.bull} tone="text-emerald-300" />
        </div>
      </header>
      <div className="prose prose-invert prose-sm max-w-none prose-headings:text-neutral-100 prose-p:text-neutral-200 prose-li:text-neutral-200 prose-strong:text-neutral-100 prose-hr:border-neutral-800 px-4 py-3">
        <ReactMarkdown>{body}</ReactMarkdown>
      </div>
    </article>
  );
}

function Target({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | null | undefined;
  tone: string;
}): JSX.Element {
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="text-[10px] text-neutral-500 uppercase tracking-wider">
        {label}
      </span>
      <span className={tone}>{formatPrice(value)}</span>
    </div>
  );
}
