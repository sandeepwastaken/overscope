import { useMemo, useState } from "react";

import { SEVERITY } from "../lib";
import type { Finding, OverscopeReport } from "../types";
import { Icon } from "../ui";

type Tab = "findings" | "json";

export function Evidence({ report, onInspect }: { report: OverscopeReport; onInspect: (p: string) => void }) {
  const [tab, setTab] = useState<Tab>("findings");
  const json = useMemo(() => JSON.stringify(stripHunks(report), null, 2), [report]);
  const [copied, setCopied] = useState(false);

  return (
    <div className="flex flex-col gap-space-md px-gutter py-margin">
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <div className="flex items-center gap-space-xs rounded-lg bg-surface-container-low p-space-xs">
          <SegBtn active={tab === "findings"} onClick={() => setTab("findings")} icon="rule" label={`Human-Readable Findings ${report.findings.length}`} />
          <SegBtn active={tab === "json"} onClick={() => setTab("json")} icon="data_object" label="Raw Audit JSON" />
        </div>
        <div className="flex items-center gap-space-sm font-label-mono text-label-mono text-on-surface-variant">
          <Icon name="verified" size={14} className="text-primary" />
          <span>Deterministic engine · {report.findings.length} findings · schema {report.schema_version}</span>
        </div>
      </div>

      {tab === "findings" ? (
        report.findings.length === 0 ? (
          <div className="flex items-center gap-space-sm rounded-xl bg-surface-container-low p-space-lg font-code-sm text-code-sm text-on-surface-variant">
            <Icon name="verified_user" size={16} className="text-primary" /> No deterministic rule violations on these changes.
          </div>
        ) : (
          <div className="flex flex-col gap-space-md">
            {report.findings.map((f, i) => <FindingCard key={i} finding={f} onInspect={onInspect} />)}
          </div>
        )
      ) : (
        <div className="overflow-hidden rounded-xl border border-outline-variant/40 bg-surface-container-lowest">
          <div className="flex items-center justify-between border-b border-outline-variant/40 px-space-md py-space-sm font-label-mono text-label-mono uppercase text-on-surface-variant">
            <span className="flex items-center gap-space-xs"><Icon name="account_tree" size={14} /> overscope --json · schema {report.schema_version}</span>
            <button
              className="app-no-drag flex items-center gap-space-xs rounded bg-surface-container px-space-md py-space-xs text-on-surface transition-colors hover:bg-surface-container-high"
              onClick={() => navigator.clipboard?.writeText(json).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1400); })}
            >
              <Icon name={copied ? "check" : "content_copy"} size={13} className={copied ? "text-primary" : ""} /> {copied ? "Copied" : "Copy JSON"}
            </button>
          </div>
          <pre className="scroll-thin max-h-[70vh] overflow-auto p-space-md font-code-sm text-code-sm leading-relaxed text-on-surface-variant">
            <JsonView value={json} />
          </pre>
        </div>
      )}
    </div>
  );
}

function FindingCard({ finding, onInspect }: { finding: Finding; onInspect: (p: string) => void }) {
  const sev = SEVERITY[finding.severity];
  const cmd = finding.path ? `git diff -- ${finding.path}` : null;
  const [copied, setCopied] = useState(false);
  return (
    <section className="flex overflow-hidden rounded-xl border border-outline-variant/40 bg-surface-container-low">
      <div className={`w-1 shrink-0 ${sev.rail}`} />
      <div className="flex-1 p-space-lg">
        <div className="flex flex-wrap items-center justify-between gap-space-sm">
          <div className="flex items-center gap-space-sm">
            <Icon name="gpp_maybe" size={16} className={sev.text} />
            <span className="font-code-sm text-code-sm font-semibold uppercase tracking-wide text-on-surface">RULE: {finding.rule_id}</span>
            <span className={`rounded-sm px-space-sm py-0.5 font-label-mono text-label-mono font-bold uppercase ${sev.badge}`}>{sev.label} severity</span>
          </div>
          {finding.path && (
            <span className="font-code-sm text-code-sm text-on-surface-variant">{finding.path}{finding.line ? `:${finding.line}` : ""}</span>
          )}
        </div>

        <div className="mt-space-md grid grid-cols-1 gap-space-md lg:grid-cols-[1fr_320px]">
          <div className="flex flex-col gap-space-sm rounded-lg bg-surface-container-lowest p-space-md">
            <div className="font-label-mono text-label-mono uppercase text-on-surface-variant">Exact Forensic Evidence</div>
            <p className="font-body-md text-body-md leading-relaxed text-on-surface">{finding.explanation}</p>
            {finding.evidence && (
              <pre className="overflow-x-auto scroll-thin rounded bg-surface-container/40 px-space-md py-space-sm font-code-sm text-code-sm text-on-surface-variant">{finding.evidence}</pre>
            )}
          </div>
          <div className="flex flex-col gap-space-sm rounded-lg bg-surface-container-lowest p-space-md">
            <div className="flex items-center justify-between font-label-mono text-label-mono uppercase text-on-surface-variant">
              <span className="flex items-center gap-space-xs"><Icon name="build" size={13} className="text-primary" /> Remediation</span>
            </div>
            <p className="font-body-sm text-body-sm leading-relaxed text-on-surface-variant">{finding.remediation}</p>
            {cmd && (
              <button
                className="app-no-drag flex items-center justify-between gap-space-sm rounded border border-outline-variant/50 bg-surface-container px-space-md py-space-xs font-code-sm text-code-sm text-on-surface-variant transition-colors hover:bg-surface-container-high"
                onClick={() => navigator.clipboard?.writeText(cmd).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1400); })}
              >
                <span className="truncate">{copied ? "Copied" : cmd}</span>
                <Icon name={copied ? "check" : "content_copy"} size={13} className={copied ? "text-primary" : ""} />
              </button>
            )}
            {finding.path && (
              <button className="app-no-drag mt-auto flex items-center justify-center gap-space-xs rounded bg-surface-container px-space-md py-space-sm font-label-ui text-label-ui text-on-surface transition-colors hover:bg-surface-container-high" onClick={() => onInspect(finding.path!)}>
                <Icon name="arrow_forward" size={14} /> Inspect in diff
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function SegBtn({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: string; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-space-xs rounded px-space-md py-space-sm font-code-sm text-code-sm transition-colors ${
        active ? "bg-surface-container-high text-on-surface" : "text-on-surface-variant hover:text-on-surface"
      }`}
    >
      <Icon name={icon} size={15} className={active ? "text-primary" : ""} /> {label}
    </button>
  );
}

function JsonView({ value }: { value: string }) {
  const html = value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/("(\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\d+(\.\d+)?/g, (m, str, _e, colon, kw) => {
      if (str) {
        const color = colon ? "var(--secondary-fixed)" : "var(--primary)";
        return `<span style="color:rgb(${color})">${str}</span>${colon ?? ""}`;
      }
      if (kw) return `<span style="color:rgb(var(--tertiary))">${m}</span>`;
      return `<span style="color:rgb(var(--secondary))">${m}</span>`;
    });
  return <code dangerouslySetInnerHTML={{ __html: html }} />;
}

function stripHunks(report: OverscopeReport) {
  return {
    ...report,
    files: report.files.map((f) => ({ ...f, change: { ...f.change, hunks: `${f.change.hunks.length} hunk(s)` } })),
  };
}
