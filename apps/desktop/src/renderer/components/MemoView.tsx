import { useState } from "react";
import ReactMarkdown from "react-markdown";
import type { ArtifactPayload } from "../types.js";

interface Props {
  artifact: ArtifactPayload;
}

interface BasketLeg {
  ticker: string;
  weight: number;
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
  basket?: {
    long?: BasketLeg[];
    short?: BasketLeg[];
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

  const [pdfStatus, setPdfStatus] = useState<"idle" | "rendering" | "saved" | "error">(
    "idle",
  );
  const [pdfMessage, setPdfMessage] = useState<string | null>(null);

  // Strip the header fields + raw BASKET block from the body since the
  // banner and basket card render them separately.
  const body = md
    .replace(
      /^\s*\*\*(Style|Anchor|Rating|Base target|Bull target|Bear target|Horizon):\*\*[^\n]*\n/gm,
      "",
    )
    .replace(/```\s*\nBASKET\n[\s\S]+?```/g, "");

  const basket = meta.basket;
  const hasBasket =
    basket && ((basket.long?.length ?? 0) > 0 || (basket.short?.length ?? 0) > 0);

  async function onExport(): Promise<void> {
    setPdfStatus("rendering");
    setPdfMessage(null);
    try {
      const ticker = (meta.ticker ?? "memo").toString().toUpperCase();
      const persona = (meta.persona ?? "report").toString();
      const basketMd = hasBasket && basket ? renderBasketMarkdown(basket) : "";
      const contentMd = body.trim() + basketMd;
      const saved = await window.api.exportMemoPdf({
        title: `${ticker} · ${persona}`,
        suggestedName: `${ticker}-${persona}.pdf`,
        contentMd,
        headerHtml: renderHeaderHtml({
          ticker,
          persona,
          rating,
          style: meta.style ?? null,
          targets,
        }),
      });
      if (saved) {
        setPdfStatus("saved");
        setPdfMessage(saved);
      } else {
        setPdfStatus("idle");
      }
    } catch (err) {
      setPdfStatus("error");
      setPdfMessage(err instanceof Error ? err.message : String(err));
    }
  }

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
        <button
          type="button"
          onClick={() => void onExport()}
          disabled={pdfStatus === "rendering"}
          title="Save the rendered memo as a PDF"
          className="ml-2 px-3 py-1 rounded text-xs bg-neutral-800 hover:bg-neutral-700 text-neutral-100 border border-neutral-700 disabled:opacity-40"
        >
          {pdfStatus === "rendering" ? "Exporting…" : "Export PDF"}
        </button>
      </header>
      {pdfStatus === "saved" && pdfMessage && (
        <div className="px-4 py-2 text-xs text-emerald-300 border-b border-emerald-900">
          Saved to {pdfMessage}
        </div>
      )}
      {pdfStatus === "error" && pdfMessage && (
        <div className="px-4 py-2 text-xs text-rose-400 border-b border-rose-900">
          PDF export failed: {pdfMessage}
        </div>
      )}
      <div className="prose prose-invert prose-sm max-w-none prose-headings:text-neutral-100 prose-p:text-neutral-200 prose-li:text-neutral-200 prose-strong:text-neutral-100 prose-hr:border-neutral-800 px-4 py-3">
        <ReactMarkdown>{body}</ReactMarkdown>
      </div>
      {hasBasket && basket && (
        <div className="border-t border-emerald-900 px-4 py-3">
          <h3 className="text-xs text-emerald-400 uppercase tracking-wide mb-2">
            Basket
          </h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <BasketLegList title="Long" rows={basket.long ?? []} tone="emerald" />
            <BasketLegList title="Short" rows={basket.short ?? []} tone="rose" />
          </div>
        </div>
      )}
    </article>
  );
}

function BasketLegList({
  title,
  rows,
  tone,
}: {
  title: string;
  rows: BasketLeg[];
  tone: "emerald" | "rose";
}): JSX.Element {
  const header = tone === "emerald" ? "text-emerald-400" : "text-rose-400";
  if (rows.length === 0) {
    return (
      <div>
        <div className={`text-xs uppercase tracking-wide mb-1 ${header}`}>
          {title}
        </div>
        <div className="text-xs text-neutral-600">(none)</div>
      </div>
    );
  }
  return (
    <div>
      <div className={`text-xs uppercase tracking-wide mb-1 ${header}`}>
        {title}
      </div>
      <ul className="flex flex-col gap-1 font-mono">
        {rows.map((r) => (
          <li
            key={`${title}-${r.ticker}`}
            className="flex justify-between text-neutral-200"
          >
            <span>{r.ticker}</span>
            <span className="text-neutral-400">{r.weight.toFixed(0)}%</span>
          </li>
        ))}
      </ul>
    </div>
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

function renderBasketMarkdown(basket: {
  long?: BasketLeg[];
  short?: BasketLeg[];
}): string {
  const longs = basket.long ?? [];
  const shorts = basket.short ?? [];
  const out: string[] = ["\n\n## Basket\n"];
  if (longs.length > 0) {
    out.push("**Long leg**\n");
    out.push("| Ticker | Weight |\n| --- | --- |");
    for (const l of longs) {
      out.push(`| ${l.ticker} | ${l.weight.toFixed(0)}% |`);
    }
    out.push("");
  }
  if (shorts.length > 0) {
    out.push("**Short leg**\n");
    out.push("| Ticker | Weight |\n| --- | --- |");
    for (const s of shorts) {
      out.push(`| ${s.ticker} | ${s.weight.toFixed(0)}% |`);
    }
  }
  return out.join("\n");
}

function renderHeaderHtml(args: {
  ticker: string;
  persona: string;
  rating: string;
  style: string | null;
  targets: { bear?: number | null; base?: number | null; bull?: number | null };
}): string {
  const targetRow = (
    label: string,
    value: number | null | undefined,
  ): string =>
    `<span style="margin-right:18px"><strong>${label}:</strong> ${
      value == null
        ? "—"
        : "$" +
          value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })
    }</span>`;
  const rating = args.rating
    ? `<span class="rating">${escapeHtml(args.rating)}</span>`
    : "";
  const styleTag = args.style
    ? `<span style="margin-left:10px;color:#666">style: ${escapeHtml(args.style)}</span>`
    : "";
  return `<div class="memo-header">
    <div style="font-size:14pt;font-weight:600;margin-bottom:6px">${escapeHtml(args.ticker)} · ${escapeHtml(args.persona)}</div>
    <div>${rating}${targetRow("Bear", args.targets.bear)}${targetRow("Base", args.targets.base)}${targetRow("Bull", args.targets.bull)}${styleTag}</div>
  </div>`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
