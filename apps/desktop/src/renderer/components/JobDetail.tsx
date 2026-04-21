import { Fragment, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { MemoView } from "./MemoView.js";
import { TranscriptView } from "./TranscriptView.js";
import type { ArtifactRow, Idea, JobDetail as JobDetailT } from "../types.js";

interface Props {
  jobId: string;
}

function parseJson(raw: string | null): Record<string, unknown> | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function formatTs(ts: string | null): string {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    return d.toLocaleString();
  } catch {
    return ts;
  }
}

export function JobDetail({ jobId }: Props): JSX.Element {
  const [detail, setDetail] = useState<JobDetailT | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRow[]>([]);
  const [ideaRows, setIdeaRows] = useState<Idea[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDetail(null);
    setArtifacts([]);
    setIdeaRows([]);

    void (async () => {
      try {
        const [job, arts] = await Promise.all([
          window.api.getJob(jobId),
          window.api.listArtifacts(jobId),
        ]);
        if (cancelled) return;
        setDetail(job);
        setArtifacts(arts);
        if (job.type === "ideation") {
          const ideas = await window.api.listIdeas({ ideationJobId: jobId });
          if (!cancelled) setIdeaRows(ideas);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (loading) {
    return <div className="text-xs text-neutral-500">loading job…</div>;
  }
  if (error) {
    return (
      <div className="text-sm text-rose-400 border border-rose-900 rounded px-3 py-2">
        {error}
      </div>
    );
  }
  if (!detail) {
    return <div className="text-xs text-neutral-500">job not found</div>;
  }

  const inputs = detail.inputs ?? {};

  return (
    <div className="flex flex-col gap-4 min-w-0">
      <header className="border border-neutral-800 rounded bg-neutral-950/60 p-4 flex flex-col gap-2">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-xs text-neutral-500 uppercase tracking-wide">
              {detail.type} job
            </div>
            <div className="font-mono text-sm text-neutral-200">{detail.id}</div>
          </div>
          <StatusPill status={detail.status} />
        </div>
        <div className="grid grid-cols-4 gap-4 text-xs">
          <Stat label="Started" value={formatTs(detail.started_at)} />
          <Stat label="Finished" value={formatTs(detail.finished_at)} />
          <Stat label="Cost" value={`$${detail.cost_usd.toFixed(4)}`} />
          <Stat
            label="Budget"
            value={`$${detail.budget_usd.toFixed(2)}`}
          />
        </div>
        {detail.error && (
          <div className="text-xs text-rose-400 border border-rose-900 rounded px-3 py-2 mt-2">
            {detail.error}
          </div>
        )}
      </header>

      <section className="border border-neutral-800 rounded bg-neutral-950/60">
        <header className="px-3 py-2 border-b border-neutral-800 text-xs text-neutral-400 uppercase tracking-wide">
          Inputs
        </header>
        <dl className="px-4 py-3 grid grid-cols-[9rem_1fr] gap-x-4 gap-y-1 text-xs font-mono">
          {Object.entries(inputs).map(([k, v]) => (
            <Fragment key={k}>
              <dt className="text-neutral-500">{k}</dt>
              <dd className="text-neutral-200 break-words">
                {typeof v === "string" ? v : JSON.stringify(v)}
              </dd>
            </Fragment>
          ))}
          {Object.keys(inputs).length === 0 && (
            <dd className="text-neutral-600">(no inputs recorded)</dd>
          )}
        </dl>
      </section>

      {artifacts.length === 0 && detail.status !== "done" && (
        <div className="text-xs text-neutral-500 border border-neutral-800 rounded px-3 py-2">
          No artifacts yet — the job may still be running or errored before
          emitting one.
        </div>
      )}

      {artifacts.map((a) => (
        <ArtifactBlock key={a.id} artifact={a} ideaRows={ideaRows} />
      ))}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div>
      <div className="text-neutral-500 uppercase tracking-wide text-[10px]">
        {label}
      </div>
      <div className="text-neutral-200 font-mono">{value}</div>
    </div>
  );
}

function StatusPill({ status }: { status: string }): JSX.Element {
  const cls =
    status === "done"
      ? "bg-emerald-900 text-emerald-100"
      : status === "running" || status === "queued"
        ? "bg-amber-900 text-amber-100"
        : "bg-rose-900 text-rose-100";
  return (
    <span className={`px-2 py-1 text-xs rounded font-mono ${cls}`}>
      {status}
    </span>
  );
}

function ArtifactBlock({
  artifact,
  ideaRows,
}: {
  artifact: ArtifactRow;
  ideaRows: Idea[];
}): JSX.Element {
  const json = parseJson(artifact.content_json);
  const payload = {
    id: artifact.id,
    job_id: artifact.job_id,
    kind: artifact.kind,
    content_md: artifact.content_md,
    content_json: json,
  };

  if (artifact.kind === "memo") return <MemoView artifact={payload} />;
  if (artifact.kind === "transcript") return <TranscriptView artifact={payload} />;

  if (artifact.kind === "ideation_outcome") {
    return (
      <article className="border border-neutral-800 rounded bg-neutral-950/60 px-4 py-3">
        <header className="flex justify-between items-baseline mb-2">
          <h3 className="text-sm font-semibold text-neutral-200">
            Ideation candidates
          </h3>
          <span className="text-xs text-neutral-500">
            {ideaRows.length} idea(s)
          </span>
        </header>
        <ul className="flex flex-col gap-2">
          {ideaRows.map((i) => (
            <li
              key={i.id}
              className="flex items-baseline gap-3 text-sm border-b border-neutral-900 py-2"
            >
              <span className="font-mono font-semibold text-neutral-100 w-16">
                {i.ticker}
              </span>
              <span className="text-xs text-neutral-500 w-24 capitalize">
                {i.persona}
              </span>
              <span className="text-neutral-300 flex-1">{i.thesis}</span>
              <span
                className={`text-xs font-mono ${
                  i.status === "approved"
                    ? "text-emerald-400"
                    : i.status === "dismissed"
                      ? "text-neutral-500"
                      : "text-amber-400"
                }`}
              >
                {i.status}
              </span>
            </li>
          ))}
        </ul>
      </article>
    );
  }

  if (artifact.kind === "backtest_report") {
    return (
      <article className="border border-emerald-900 rounded bg-emerald-950/20 px-4 py-3">
        <header className="flex justify-between items-baseline mb-2">
          <h3 className="text-sm font-semibold text-emerald-300">
            Backtest report
          </h3>
        </header>
        <div className="prose prose-invert prose-sm max-w-none prose-headings:text-neutral-100 prose-table:text-xs">
          <ReactMarkdown>{artifact.content_md ?? ""}</ReactMarkdown>
        </div>
      </article>
    );
  }

  return (
    <article className="border border-neutral-800 rounded bg-neutral-950/60 px-4 py-3">
      <header className="text-xs text-neutral-400 uppercase tracking-wide mb-2">
        {artifact.kind}
      </header>
      <pre className="text-xs font-mono whitespace-pre-wrap text-neutral-200">
        {artifact.content_md ?? JSON.stringify(json, null, 2)}
      </pre>
    </article>
  );
}
