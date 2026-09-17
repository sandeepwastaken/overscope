import { useState } from "react";

import { agentDisplay, statusMeta } from "../lib";
import type { Reconciliation, OverscopeReport } from "../types";
import { Icon } from "../ui";

export function Claims({ report, onInspect }: { report: OverscopeReport; onInspect: (p: string) => void }) {
  const recs = report.reconciliations;
  const supported = recs.filter((r) => r.status === "SUPPORTED").length;
  const mismatch = recs.filter((r) => r.status === "MISMATCH").length;
  const unverified = recs.filter((r) => r.status === "UNVERIFIED" || r.status === "INSUFFICIENT_EVIDENCE").length;
  const total = recs.length || 1;
  const reliability = Math.round((supported / total) * 100);
  const [filter, setFilter] = useState<string>("ALL");

  const shown = recs.filter((r) => filter === "ALL" || r.status === filter || (filter === "UNVERIFIED" && r.status === "INSUFFICIENT_EVIDENCE"));

  return (
    <div className="flex flex-col gap-space-lg px-gutter py-margin">
      <section className="flex flex-col gap-space-md rounded-xl bg-surface-container-low p-space-lg">
        <div className="flex flex-wrap items-center justify-between gap-space-sm">
          <div className="flex items-center gap-space-sm">
            <Icon name="fact_check" size={20} className="text-on-surface" />
            <h2 className="font-headline-md text-headline-md text-on-surface">Claims Ledger</h2>
            <span className="rounded-sm bg-surface-container-high px-space-sm py-0.5 font-label-mono text-label-mono uppercase text-on-surface-variant">Strict</span>
            {mismatch > 0 && (
              <span className="rounded-sm bg-error-container px-space-sm py-0.5 font-label-mono text-label-mono font-bold uppercase text-on-error-container">{mismatch} contradiction{mismatch === 1 ? "" : "s"}</span>
            )}
          </div>
          <span className="flex items-center gap-space-xs font-label-mono text-label-mono text-on-surface-variant">
            <Icon name="verified" size={14} className="text-primary" /> Deterministic cross-reference
          </span>
        </div>
        <p className="font-body-md text-body-md text-on-surface-variant">
          {agentDisplay(report.agent)}’s natural-language commitments vs. the uncommitted working-tree truth.
        </p>

        <div className="flex flex-col gap-space-sm">
          <div className="flex flex-wrap items-center justify-between gap-space-sm font-label-mono text-label-mono">
            <span className="text-on-surface-variant">
              CLAIMS INTEGRITY SCORE: <span className={reliability >= 80 ? "text-primary" : reliability >= 50 ? "text-tertiary" : "text-error"}>{reliability}% RELIABILITY</span> · {recs.length} extracted statements
            </span>
            <span className="flex items-center gap-space-md">
              <Legend dot="bg-error" label={`Mismatches ${mismatch}`} />
              <Legend dot="bg-primary" label={`Supported ${supported}`} />
              <Legend dot="bg-tertiary-container" label={`Unverified ${unverified}`} />
            </span>
          </div>
          <div className="flex h-2 overflow-hidden rounded-sm bg-surface-container-lowest">
            {mismatch > 0 && <span className="bg-error" style={{ width: `${(mismatch / total) * 100}%` }} />}
            {supported > 0 && <span className="bg-primary" style={{ width: `${(supported / total) * 100}%` }} />}
            {unverified > 0 && <span className="bg-tertiary-container" style={{ width: `${(unverified / total) * 100}%` }} />}
          </div>
        </div>

        <div className="flex items-center gap-space-xs rounded-lg bg-surface-container-lowest p-space-xs font-label-mono text-label-mono">
          {([["ALL", `All ${recs.length}`], ["MISMATCH", `Mismatches ${mismatch}`], ["SUPPORTED", `Supported ${supported}`], ["UNVERIFIED", `Unverified ${unverified}`]] as [string, string][]).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setFilter(id)}
              className={`rounded px-space-md py-space-xs transition-colors ${filter === id ? "bg-surface-container-high text-on-surface" : "text-on-surface-variant hover:text-on-surface"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      {recs.length === 0 ? (
        <div className="flex items-center gap-space-sm rounded-xl bg-surface-container-low p-space-lg font-code-sm text-code-sm text-on-surface-variant">
          <Icon name="info" size={16} /> The agent’s final message made no narrow, verifiable claims.
        </div>
      ) : (
        <div className="flex flex-col gap-space-md">
          {shown.map((rec, i) => (
            <ClaimRow key={i} rec={rec} index={i + 1} report={report} onInspect={onInspect} />
          ))}
        </div>
      )}
    </div>
  );
}

function ClaimRow({ rec, index, report, onInspect }: { rec: Reconciliation; index: number; report: OverscopeReport; onInspect: (p: string) => void }) {
  const meta = statusMeta(rec.status);
  const isMismatch = rec.status === "MISMATCH";
  const [open, setOpen] = useState(isMismatch);
  const evidencePath = rec.evidence?.split(",")[0]?.trim();
  const pathIsFile = evidencePath && report.files.some((f) => f.change.path === evidencePath);

  return (
    <section className="overflow-hidden rounded-xl border border-outline-variant/40 bg-surface-container-low">
      <button className="app-no-drag flex w-full items-center gap-space-md px-space-lg py-space-md text-left" onClick={() => setOpen((o) => !o)}>
        <span className={`grid h-6 w-6 shrink-0 place-items-center rounded ${meta.badge}`}>
          <Icon name={meta.icon} size={14} />
        </span>
        <span className={`rounded-sm px-space-sm py-0.5 font-label-mono text-label-mono font-bold uppercase ${meta.badge}`}>
          {meta.label} #{String(index).padStart(2, "0")}
        </span>
        <span className="flex-1 truncate font-code-sm text-code-sm text-on-surface">{rec.claim}: {rec.explanation}</span>
        <Icon name={open ? "expand_less" : "expand_more"} size={18} className="shrink-0 text-on-surface-variant" />
      </button>

      {open && (
        <div className="grid grid-cols-1 gap-space-md border-t border-outline-variant/40 p-space-lg lg:grid-cols-2">
          <div className="flex flex-col gap-space-sm rounded-lg bg-surface-container-lowest p-space-md">
            <div className="flex items-center justify-between font-label-mono text-label-mono uppercase text-on-surface-variant">
              <span className="flex items-center gap-space-xs"><Icon name="smart_toy" size={14} /> Agent Statement</span>
              <span>{agentDisplay(report.agent)}</span>
            </div>
            <p className="font-code-md text-code-md italic leading-relaxed text-on-surface">“{rec.claim}”</p>
          </div>
          <div className="flex flex-col gap-space-sm rounded-lg bg-surface-container-lowest p-space-md">
            <div className="flex items-center justify-between font-label-mono text-label-mono uppercase text-on-surface-variant">
              <span className="flex items-center gap-space-xs"><Icon name="difference" size={14} /> Deterministic Git Evidence</span>
              {isMismatch && <span className="rounded-sm bg-error-container px-space-sm py-0.5 text-on-error-container">Contradiction</span>}
            </div>
            <p className="font-body-md text-body-md leading-relaxed text-on-surface-variant">{rec.explanation}</p>
            {rec.evidence && <p className="rounded bg-surface-container/40 px-space-sm py-space-xs font-code-sm text-code-sm text-on-surface-variant">{rec.evidence}</p>}
            <div className="mt-auto flex items-center justify-between pt-space-xs">
              <span className={`flex items-center gap-space-xs font-label-mono text-label-mono ${meta.text}`}>
                <Icon name={meta.icon} size={14} /> Verdict: {meta.label}
              </span>
              {pathIsFile && (
                <button className="app-no-drag rounded bg-surface-container px-space-md py-space-xs font-label-ui text-label-ui text-on-surface transition-colors hover:bg-surface-container-high" onClick={() => onInspect(evidencePath!)}>
                  View Evidence Diff
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function Legend({ dot, label }: { dot: string; label: string }) {
  return (
    <span className="flex items-center gap-space-xs text-on-surface-variant">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} /> {label}
    </span>
  );
}
