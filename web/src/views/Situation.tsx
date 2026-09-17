import type { RepositoryStatus, GitAction } from "../bridge";
import {
  SCOPE,
  SEVERITY,
  agentDisplay,
  authorLabel,
  driftLabel,
  findingsFor,
  riskScore,
  scopeDistribution,
  sortedFiles,
  totals,
  verdict,
} from "../lib";
import type { ReactNode } from "react";

import type { Finding, OverscopeReport } from "../types";
import { Icon } from "../ui";

export function Situation({
  report,
  status,
  gitBusy,
  onGitAction,
  onInspect,
}: {
  report: OverscopeReport;
  status: RepositoryStatus | null;
  gitBusy: GitAction | null;
  onGitAction: (a: GitAction) => void;
  onInspect: (path: string) => void;
}) {
  const v = verdict(report);
  const { additions, deletions } = totals(report);
  const risk = riskScore(report);
  const high = report.findings.filter((f) => f.severity === "HIGH").length;
  const outFiles = report.files.filter((f) => f.scope === "OUT_OF_SCOPE");
  const mismatches = report.reconciliations.filter((r) => r.status === "MISMATCH").length;
  const lead =
    report.findings.find((f) => f.severity === "HIGH") ??
    report.findings.find((f) => f.severity === "MEDIUM") ??
    null;
  const dist = scopeDistribution(report);

  return (
    <div className="flex flex-col gap-space-lg px-gutter py-margin">

      <section className="flex flex-col gap-space-md rounded-xl bg-surface-container-low p-space-lg">
        <div className="flex flex-col items-start justify-between gap-space-md pb-space-sm md:flex-row md:items-center">
          <div className="flex items-center gap-space-md">
            <span className={`flex items-center gap-space-xs rounded-lg px-space-md py-space-xs font-label-mono text-label-mono font-semibold uppercase tracking-wider ${v.badge}`}>
              <Icon name={v.icon} size={16} className={v.text} /> {v.label}
            </span>
            <span className="flex items-center gap-space-xs font-label-mono text-label-mono text-on-surface-variant">
              GATE-REF: <span className="text-on-surface">#{report.session_id.slice(0, 18)}</span>
            </span>
          </div>
          <div className="flex items-center gap-space-sm">
            <button
              className="app-no-drag flex items-center gap-space-xs rounded-lg bg-error-container/40 px-space-md py-space-xs font-label-ui text-label-ui text-on-error-container transition-colors hover:bg-error-container disabled:opacity-40"
              onClick={() => outFiles[0] && onInspect(outFiles[0].change.path)}
              disabled={outFiles.length === 0}
              title="Jump to the first out-of-scope change"
            >
              <Icon name="block" size={14} /> Inspect Outliers ({outFiles.length})
            </button>
            {status?.remote ? (
              <button
                className="app-no-drag flex items-center gap-space-xs rounded-lg bg-primary px-space-md py-space-xs font-headline-sm text-headline-sm font-semibold text-on-primary transition-colors hover:bg-primary-fixed disabled:opacity-50"
                onClick={() => onGitAction("push")}
                disabled={gitBusy !== null || !status.upstream}
                title={status.upstream ? `Push to ${status.remote.name} via ${status.remote.transport}` : "No upstream configured"}
              >
                {gitBusy === "push" ? <Icon name="progress_activity" size={16} className="animate-spin" /> : <Icon name="cloud_upload" size={16} />}
                Push {status.ahead > 0 ? `(${status.ahead})` : ""}
              </button>
            ) : (
              <button className="app-no-drag flex items-center gap-space-xs rounded-lg bg-surface-container px-space-md py-space-xs font-headline-sm text-headline-sm text-on-surface-variant" disabled title="No git remote configured">
                <Icon name="cloud_off" size={16} /> No Remote
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-col justify-between gap-space-lg rounded-lg bg-surface-container-lowest p-space-lg lg:flex-row lg:items-center">
          <div className="flex max-w-3xl flex-col gap-space-xs">
            <div className="flex items-center gap-space-xs">
              <Icon name="gavel" size={18} className={v.text} />
              <h2 className="font-headline-md text-headline-md text-on-surface">{lead ? `${lead.title} detected` : "Change audit complete"}</h2>
            </div>
            <p className="font-body-md text-body-md leading-relaxed text-on-surface-variant">
              {lead ? (
                <>
                  {agentDisplay(report.agent)} — {lead.explanation}{" "}
                  {lead.path && <code className="rounded bg-surface-container px-1 py-0.5 font-code-sm text-code-sm text-error">{lead.path}</code>}
                </>
              ) : (
                report.summary
              )}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-space-md rounded-lg bg-surface-container-low px-space-md py-space-sm">
            <RiskGauge score={risk} tone={v.tone} />
            <div className="flex flex-col">
              <span className="font-label-mono text-label-mono uppercase text-on-surface-variant">Drift Score</span>
              <span className={`font-headline-sm text-headline-sm ${v.text}`}>{driftLabel(risk)}</span>
            </div>
          </div>
        </div>


        <div className="grid grid-cols-2 gap-space-md pt-space-xs sm:grid-cols-3 lg:grid-cols-5">
          <Metric label="Changed Files" labelClass="text-on-surface-variant" value={String(report.files.length)} unit="files" valueClass="text-on-surface">
            <span className="font-code-sm text-code-sm text-primary">+{additions} <span className="text-error">-{deletions}</span></span>
          </Metric>
          <Metric label="High-Severity" labelClass="text-error" value={String(high)} unit={high === 1 ? "finding" : "findings"} valueClass="text-error" caption={high ? "Critical outlier" : "None detected"} />
          <Metric label="Out-of-Scope" labelClass="text-tertiary" value={String(outFiles.length)} unit="paths" valueClass="text-tertiary" caption={outFiles.map((f) => f.change.path).slice(0, 2).join(", ") || "None"} />
          <Metric label="Claim Mismatches" labelClass="text-secondary" value={String(mismatches)} unit="diffs" valueClass="text-secondary-fixed" caption={mismatches ? "Silent side-effects" : "Consistent"} />
          <Metric label="Intent Confidence" labelClass="text-on-surface-variant" value={`${Math.round(report.intent.confidence * 100)}%`} unit="" valueClass="text-primary" caption="Heuristic intent trace" wide />
        </div>
      </section>


      <section className="flex flex-col gap-space-md rounded-xl bg-surface-container-low p-space-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-space-sm">
            <Icon name="terminal" size={16} className="text-primary" />
            <h3 className="font-headline-sm text-headline-sm font-semibold uppercase tracking-wider text-on-surface">User Intent Contract (Transcript Reference)</h3>
          </div>
          <div className="flex items-center gap-space-xs rounded bg-surface-container px-space-md py-space-xs font-label-mono text-label-mono text-on-surface-variant">
            <span>RUN:</span>
            <span className="font-semibold text-on-surface">#{report.session_id.slice(0, 12)}</span>
            <span>•</span>
            <span>AGENT: {agentDisplay(report.agent)}</span>
          </div>
        </div>
        <div className="flex flex-col gap-space-sm rounded-lg bg-surface-container-lowest p-space-lg">
          <div className="flex items-center gap-space-xs font-label-mono text-label-mono text-on-surface-variant">
            <Icon name="format_quote" size={14} /> VERBATIM INSTRUCTION STRING:
          </div>
          <p className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded bg-surface-container/20 py-space-sm pl-space-md font-code-md text-code-md leading-relaxed text-on-surface scroll-thin">
            “{report.intent.text}”
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-space-sm pt-space-xs">
          {report.intent.operation && (
            <Pill label="OP:" value={report.intent.operation.toUpperCase()} valueClass="text-secondary" />
          )}
          {report.intent.paths.length > 0 && (
            <div className="flex items-center gap-space-xs rounded bg-surface-container px-space-md py-space-xs font-label-mono text-label-mono text-on-surface">
              <span className="text-on-surface-variant">TARGETS:</span>
              {report.intent.paths.slice(0, 3).map((p, i) => (
                <span key={p} className="font-semibold text-primary">{p}{i < Math.min(report.intent.paths.length, 3) - 1 ? "," : ""}</span>
              ))}
            </div>
          )}
          {report.intent.avoid.length > 0 && (
            <div className="flex items-center gap-space-xs rounded bg-error-container px-space-md py-space-xs font-label-mono text-label-mono font-semibold text-on-error-container">
              <Icon name="do_not_disturb_on" size={14} className="text-error" />
              <span>NEGATIVE CONSTRAINT: DO NOT TOUCH {report.intent.avoid.join(", ")}</span>
            </div>
          )}
          <div className="ml-auto flex items-center gap-space-xs rounded bg-surface-container px-space-md py-space-xs font-label-mono text-label-mono text-on-surface-variant">
            <Icon name="check_circle" size={14} className="text-primary" />
            <span>Parser Confidence: <strong className="text-on-surface">{Math.round(report.intent.confidence * 100)}%</strong></span>
          </div>
        </div>
      </section>


      <section className="flex flex-col gap-space-md rounded-xl bg-surface-container-low p-space-lg">
        <div className="flex flex-col justify-between gap-space-sm sm:flex-row sm:items-center">
          <div className="flex flex-col gap-space-xs">
            <div className="flex items-center gap-space-sm">
              <Icon name="data_exploration" size={18} className="text-on-surface" />
              <h3 className="font-headline-sm text-headline-sm text-on-surface">Proportional Scope Distribution</h3>
            </div>
            <span className="font-body-sm text-body-sm text-on-surface-variant">Computed from the working tree relative to the extracted intent boundary.</span>
          </div>
          <div className="flex flex-wrap items-center gap-space-md font-label-mono text-label-mono">
            {dist.map(({ status: s, pct }) => (
              <div key={s} className="flex items-center gap-space-xs">
                <span className={`inline-block h-2.5 w-2.5 rounded-sm ${SCOPE[s].dot}`} />
                <span className={s === "OUT_OF_SCOPE" ? "font-semibold text-error" : "text-on-surface"}>{SCOPE[s].label} ({pct}%)</span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex h-3 w-full overflow-hidden rounded-lg bg-surface-container-lowest">
          {dist.map(({ status: s, count, pct }) =>
            count > 0 ? <div key={s} className={`h-full ${SCOPE[s].bar}`} style={{ width: `${pct}%` }} title={`${SCOPE[s].label}: ${count}`} /> : null,
          )}
        </div>
        <div className="mt-space-sm flex flex-col gap-space-xs">
          <div className="grid grid-cols-12 px-space-md py-space-xs font-label-mono text-label-mono uppercase tracking-wider text-on-surface-variant">
            <div className="col-span-5 sm:col-span-4">File Path &amp; Classification</div>
            <div className="col-span-2 hidden sm:block">Delta &amp; Author</div>
            <div className="col-span-5 sm:col-span-5">Audit Synopsis</div>
            <div className="col-span-2 text-right sm:col-span-1">Action</div>
          </div>
          {sortedFiles(report.files).map((file) => {
            const meta = SCOPE[file.scope];
            return (
              <div key={file.change.path} className="grid grid-cols-12 items-center gap-space-xs rounded-lg bg-surface-container px-space-md py-space-sm transition-colors hover:bg-surface-container-high">
                <div className="col-span-5 flex items-center gap-space-sm overflow-hidden sm:col-span-4">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${meta.dot}`} />
                  <div className="flex min-w-0 flex-col">
                    <span className={`truncate font-code-sm text-code-sm font-semibold ${file.scope === "OUT_OF_SCOPE" ? "text-error" : "text-on-surface"}`}>{file.change.path}</span>
                    <span className={`font-label-mono text-label-mono uppercase ${meta.text}`}>{meta.label}</span>
                  </div>
                </div>
                <div className="col-span-2 hidden flex-col sm:flex">
                  <span className="font-code-sm text-code-sm text-on-surface">+{file.change.additions} <span className="text-error">-{file.change.deletions}</span></span>
                  <span className="font-label-ui text-label-ui text-on-surface-variant">{authorLabel(file.attribution, report.agent)}</span>
                </div>
                <div className="col-span-5 pr-space-sm font-body-sm text-body-sm leading-snug text-on-surface-variant sm:col-span-5">
                  {file.reasons[0] ?? "No scope evidence."}
                </div>
                <div className="col-span-2 text-right sm:col-span-1">
                  <button className="app-no-drag inline-flex items-center gap-space-xs font-label-ui text-label-ui text-secondary-fixed transition-colors hover:text-secondary" onClick={() => onInspect(file.change.path)}>
                    Inspect <Icon name="arrow_forward" size={13} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>


      <div className="grid grid-cols-1 gap-space-lg lg:grid-cols-3">
        <section className="flex flex-col gap-space-md rounded-xl bg-surface-container-low p-space-lg lg:col-span-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-space-sm">
              <Icon name="policy" size={18} className="text-on-surface" />
              <h3 className="font-headline-sm text-headline-sm text-on-surface">Deterministic Policy Violations</h3>
            </div>
            {report.findings.length > 0 && (
              <span className="rounded bg-error-container/60 px-space-md py-space-xs font-label-mono text-label-mono font-semibold uppercase text-on-error-container">
                {report.findings.filter((f) => f.severity === "HIGH" || f.severity === "MEDIUM").length} Active Alerts
              </span>
            )}
          </div>
          {report.findings.length === 0 ? (
            <div className="flex items-center gap-space-sm rounded-lg bg-surface-container-lowest px-space-md py-space-lg font-code-sm text-code-sm text-on-surface-variant">
              <Icon name="verified_user" size={16} className="text-primary" /> No deterministic rule violations on these changes.
            </div>
          ) : (
            report.findings.slice(0, 6).map((finding, i) => <Violation key={i} finding={finding} onInspect={onInspect} />)
          )}
        </section>

        <section className="flex flex-col gap-space-md rounded-xl bg-surface-container-low p-space-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-space-sm">
              <Icon name="priority_high" size={18} className="text-tertiary" />
              <h3 className="font-headline-sm text-headline-sm text-on-surface">Review First</h3>
            </div>
            <span className="font-label-mono text-label-mono uppercase text-on-surface-variant">Pre-Commit Queue</span>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Ranked priority list of files to inspect before you type <code className="rounded bg-surface-container px-1 py-0.5 font-code-sm text-code-sm text-on-surface">git commit</code>.
          </p>
          <div className="flex flex-col gap-space-sm">
            {report.review_first.map((path, i) => (
              <ReviewItem key={path} rank={i + 1} path={path} report={report} onInspect={onInspect} />
            ))}
            {report.review_first.length === 0 && (
              <div className="rounded-lg bg-surface-container-lowest px-space-md py-space-md font-code-sm text-code-sm text-on-surface-variant">Nothing stands out for priority review.</div>
            )}
          </div>
          {report.review_first.length > 0 && (
            <div className="mt-space-xs flex items-center gap-space-xs rounded-lg bg-surface-container-lowest px-space-md py-space-sm font-label-mono text-label-mono text-on-surface-variant">
              <Icon name="keyboard_return" size={14} className="text-primary" /> Enter to inspect #1
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Metric({
  label,
  labelClass,
  value,
  unit,
  valueClass,
  caption,
  wide,
  children,
}: {
  label: string;
  labelClass: string;
  value: string;
  unit: string;
  valueClass: string;
  caption?: string;
  wide?: boolean;
  children?: ReactNode;
}) {
  return (
    <div className={`flex flex-col rounded-lg bg-surface-container p-space-md ${wide ? "col-span-2 sm:col-span-1" : ""}`}>
      <span className={`font-label-mono text-label-mono uppercase ${labelClass}`}>{label}</span>
      <span className={`mt-space-xs font-headline-lg text-headline-lg ${valueClass}`}>
        {value} {unit && <span className="font-code-sm text-code-sm font-normal text-on-surface-variant">{unit}</span>}
      </span>
      <span className="mt-space-xs font-label-ui text-label-ui text-on-surface-variant">
        {children ?? caption}
      </span>
    </div>
  );
}

function Pill({ label, value, valueClass }: { label: string; value: string; valueClass: string }) {
  return (
    <div className="flex items-center gap-space-xs rounded bg-surface-container px-space-md py-space-xs font-label-mono text-label-mono text-on-surface">
      <span className="text-on-surface-variant">{label}</span>
      <span className={`font-semibold ${valueClass}`}>{value}</span>
    </div>
  );
}

function RiskGauge({ score, tone }: { score: number; tone: string }) {
  const color = tone === "clean" ? "text-primary" : tone === "review" ? "text-tertiary" : "text-error";
  return (
    <div className="relative flex h-11 w-11 items-center justify-center">
      <svg className="h-11 w-11 -rotate-90" viewBox="0 0 36 36">
        <path className="text-surface-container-highest" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3.5" />
        <path className={color} d={`M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831`} fill="none" stroke="currentColor" strokeDasharray={`${score}, 100`} strokeLinecap="round" strokeWidth="3.5" />
      </svg>
      <span className={`absolute font-label-mono text-label-mono font-bold ${color}`}>{score}</span>
    </div>
  );
}

function Violation({ finding, onInspect }: { finding: Finding; onInspect: (path: string) => void }) {
  const sev = SEVERITY[finding.severity];
  const critical = finding.severity === "HIGH";
  return (
    <div className="flex flex-col gap-space-sm rounded-lg bg-surface-container-lowest p-space-md">
      <div className="flex flex-wrap items-center gap-space-sm">
        <span className={`rounded px-space-sm py-0.5 font-label-mono text-label-mono font-bold uppercase ${critical ? "bg-error-container text-on-error-container" : "bg-tertiary-container/30 text-tertiary"}`}>
          {critical ? "Critical" : sev.label}
        </span>
        <span className="font-code-sm text-code-sm font-semibold uppercase text-on-surface-variant">Rule {finding.rule_id}</span>
        {finding.path && (
          <span className="font-code-sm text-code-sm text-on-surface">
            {finding.path}{finding.line ? `:${finding.line}` : ""}
          </span>
        )}
      </div>
      <p className="font-body-md text-body-md leading-snug text-on-surface">“{finding.explanation}”</p>
      {finding.evidence && <p className="rounded bg-surface-container/40 px-space-sm py-space-xs font-code-sm text-code-sm text-on-surface-variant">{finding.evidence}</p>}
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          <span className="font-semibold uppercase text-on-surface-variant">Recommendation:</span> {finding.remediation}
        </p>
        {finding.path && (
          <button className="app-no-drag shrink-0 rounded bg-surface-container px-space-md py-space-xs font-label-ui text-label-ui text-on-surface transition-colors hover:bg-surface-container-high" onClick={() => onInspect(finding.path!)}>
            Inspect Hunk
          </button>
        )}
      </div>
    </div>
  );
}

function ReviewItem({ rank, path, report, onInspect }: { rank: number; path: string; report: OverscopeReport; onInspect: (p: string) => void }) {
  const file = report.files.find((f) => f.change.path === path);
  const findings = findingsFor(report, path);
  const tags: { label: string; cls: string }[] = [];
  if (file && file.scope === "OUT_OF_SCOPE") tags.push({ label: "Out of scope", cls: "bg-error-container/40 text-on-error-container" });
  const worst = findings[0];
  if (worst) tags.push({ label: worst.title, cls: SEVERITY[worst.severity].badge });
  if (file && file.attribution === "UNATTRIBUTED") tags.push({ label: "Not this session", cls: "bg-tertiary-container/20 text-tertiary" });
  return (
    <button className="app-no-drag flex flex-col gap-space-xs rounded-lg bg-surface-container-lowest p-space-md text-left transition-colors hover:bg-surface-container" onClick={() => onInspect(path)}>
      <div className="flex items-center gap-space-sm">
        <span className="grid h-5 w-5 place-items-center rounded bg-surface-container-high font-label-mono text-label-mono font-bold text-tertiary">{rank}</span>
        <span className="flex-1 truncate font-code-sm text-code-sm text-on-surface">{path}</span>
        <Icon name="chevron_right" size={16} className="text-on-surface-variant" />
      </div>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-space-xs pl-7">
          {tags.map((t, i) => (
            <span key={i} className={`rounded-sm px-space-sm py-0.5 font-label-mono text-label-mono ${t.cls}`}>{t.label}</span>
          ))}
        </div>
      )}
    </button>
  );
}
