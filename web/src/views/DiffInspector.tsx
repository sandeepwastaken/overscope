import { useMemo, useState } from "react";

import {
  SCOPE,
  SEVERITY,
  agentDisplay,
  authorLabel,
  findingsFor,
  statusLabel,
} from "../lib";
import type { DiffHunk, ScopeStatus, ScopedFile, OverscopeReport } from "../types";
import { Icon, ScopeBar } from "../ui";

type Filter = "ALL" | "OUT_OF_SCOPE" | "IN_SCOPE" | "ADJACENT";

interface Row {
  kind: "add" | "del" | "ctx";
  old: number | null;
  neu: number | null;
  text: string;
}

function hunkRows(hunk: DiffHunk): Row[] {
  let oldN = hunk.old_start ?? 0;
  let newN = hunk.new_start ?? 0;
  return hunk.lines
    .filter((l) => !l.startsWith("\\"))
    .map((line) => {
      const sign = line[0];
      const text = line.slice(1);
      if (sign === "+") return { kind: "add", old: null, neu: newN++, text };
      if (sign === "-") return { kind: "del", old: oldN++, neu: null, text };
      return { kind: "ctx", old: oldN++, neu: newN++, text };
    });
}

export function DiffInspector({
  report,
  selectedPath,
  onSelect,
  onReveal,
}: {
  report: OverscopeReport;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  onReveal: (path: string) => void;
}) {
  const [filter, setFilter] = useState<Filter>("ALL");
  const [query, setQuery] = useState("");

  const counts = {
    ALL: report.files.length,
    OUT_OF_SCOPE: report.files.filter((f) => f.scope === "OUT_OF_SCOPE").length,
    IN_SCOPE: report.files.filter((f) => f.scope === "IN_SCOPE").length,
    ADJACENT: report.files.filter((f) => f.scope === "ADJACENT").length,
  };

  const files = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return report.files.filter(
      (f) =>
        (filter === "ALL" || f.scope === filter) &&
        (!needle || f.change.path.toLowerCase().includes(needle)),
    );
  }, [report.files, filter, query]);

  const selected = report.files.find((f) => f.change.path === selectedPath) ?? files[0] ?? report.files[0] ?? null;

  return (
    <div className="flex h-full flex-col">

      <div className="flex flex-col gap-space-sm border-b border-outline-variant/40 bg-surface-container-low px-gutter py-space-md">
        <div className="flex flex-wrap items-center justify-between gap-space-sm">
          <div className="flex items-center gap-space-sm">
            <Icon name="account_tree" size={18} className="text-primary" />
            <h2 className="font-headline-sm text-headline-sm font-semibold uppercase tracking-wider text-on-surface">Diff Forensic Workbench</h2>
          </div>
          <div className="flex items-center gap-space-md font-label-mono text-label-mono">
            {(["IN_SCOPE", "ADJACENT", "OUT_OF_SCOPE"] as ScopeStatus[]).map((s) => (
              <span key={s} className="flex items-center gap-space-xs">
                <span className={`h-2 w-2 rounded-sm ${SCOPE[s].dot}`} />
                <span className={s === "OUT_OF_SCOPE" ? "text-error" : "text-on-surface-variant"}>
                  {SCOPE[s].label}: {report.files.length ? Math.round((counts[s === "OUT_OF_SCOPE" ? "OUT_OF_SCOPE" : s === "IN_SCOPE" ? "IN_SCOPE" : "ADJACENT"] / report.files.length) * 100) : 0}%
                </span>
              </span>
            ))}
          </div>
        </div>
        <ScopeBar report={report} className="h-2.5 rounded-lg" />
      </div>


      <div className="grid min-h-0 flex-1 grid-cols-[300px_minmax(0,1fr)_320px] gap-0">

        <div className="flex min-h-0 flex-col gap-space-sm overflow-hidden border-r border-outline-variant/40 bg-surface-container-low p-space-md">
          <label className="flex items-center gap-space-xs rounded-lg bg-surface-container-lowest px-space-md py-space-sm">
            <Icon name="filter_list" size={15} className="text-on-surface-variant" />
            <input
              className="w-full bg-transparent font-code-sm text-code-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none"
              placeholder="Filter changed files…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <div className="flex items-center gap-space-xs rounded-lg bg-surface-container-lowest p-space-xs font-label-mono text-label-mono">
            {([["ALL", "All"], ["OUT_OF_SCOPE", "Out"], ["IN_SCOPE", "In"], ["ADJACENT", "Adj"]] as [Filter, string][]).map(([id, label]) => (
              <button
                key={id}
                onClick={() => setFilter(id)}
                className={`flex flex-1 items-center justify-center gap-space-xs rounded px-space-sm py-space-xs transition-colors ${
                  filter === id ? "bg-surface-container-high text-on-surface" : "text-on-surface-variant hover:text-on-surface"
                }`}
              >
                {id === "OUT_OF_SCOPE" && <span className="h-1.5 w-1.5 rounded-full bg-error" />}
                {label} <span className="text-on-surface-variant">{counts[id]}</span>
              </button>
            ))}
          </div>
          <div className="scroll-thin flex min-h-0 flex-1 flex-col gap-space-xs overflow-y-auto">
            {files.map((file) => (
              <FileCard key={file.change.path} file={file} active={selected?.change.path === file.change.path} onSelect={() => onSelect(file.change.path)} />
            ))}
            {files.length === 0 && <div className="px-space-md py-space-md font-code-sm text-code-sm text-on-surface-variant">No files match.</div>}
          </div>
          <div className="flex flex-col gap-space-xs rounded-lg border border-outline-variant/40 bg-surface-container-lowest p-space-md font-label-mono text-label-mono">
            <Info k="Run Agent ID" val={`#${report.session_id.slice(0, 12)}`} />
            <Info k="Agent" val={agentDisplay(report.agent)} valClass="text-primary" />
            <Info k="Worktree SHA" val={report.head ? `${report.head.slice(0, 10)}` : "uncommitted"} />
          </div>
        </div>


        <div className="scroll-thin min-h-0 overflow-auto bg-surface">
          {selected ? <DiffView file={selected} /> : <Empty />}
        </div>


        <div className="scroll-thin min-h-0 overflow-y-auto border-l border-outline-variant/40 bg-surface-container-low p-space-md">
          {selected ? <Inspector report={report} file={selected} onReveal={onReveal} /> : null}
        </div>
      </div>
    </div>
  );
}

function FileCard({ file, active, onSelect }: { file: ScopedFile; active: boolean; onSelect: () => void }) {
  const meta = SCOPE[file.scope];
  const st = statusLabel(file.change);
  return (
    <button
      onClick={onSelect}
      className={`flex flex-col gap-space-xs rounded-lg border px-space-md py-space-sm text-left transition-colors ${
        active ? "border-outline-variant bg-surface-container" : "border-transparent hover:bg-surface-container"
      }`}
    >
      <div className="flex items-center justify-between gap-space-sm">
        <span className="flex items-center gap-space-xs overflow-hidden">
          <Icon name={fileIcon(file.change.kind)} size={14} className="shrink-0 text-on-surface-variant" />
          <span className={`truncate font-code-sm text-code-sm ${file.scope === "OUT_OF_SCOPE" ? "text-error" : "text-on-surface"}`}>{file.change.path}</span>
        </span>
        <span className="shrink-0 rounded-sm bg-surface-container-high px-space-sm py-0.5 font-label-mono text-label-mono uppercase text-on-surface-variant">{st}</span>
      </div>
      <div className="flex items-center justify-between">
        <span className={`flex items-center gap-space-xs font-label-mono text-label-mono uppercase ${meta.text}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} /> {meta.label}
        </span>
        <span className="font-code-sm text-code-sm text-on-surface-variant">
          <span className="text-primary">+{file.change.additions}</span> <span className="text-error">-{file.change.deletions}</span>
        </span>
      </div>
    </button>
  );
}

function DiffView({ file }: { file: ScopedFile }) {
  const c = file.change;
  return (
    <div className="flex flex-col">
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-space-md border-b border-outline-variant/40 bg-surface-container-low px-space-md py-space-sm">
        <div className="flex items-center gap-space-xs">
          {file.scope === "OUT_OF_SCOPE" && <Icon name="warning" size={16} className="text-error" />}
          <span className="font-code-sm text-code-sm font-semibold text-on-surface">{c.path}</span>
          <span className="rounded-sm bg-surface-container-high px-space-sm py-0.5 font-label-mono text-label-mono uppercase text-on-surface-variant">{statusLabel(c)}</span>
        </div>
        <span className="font-label-mono text-label-mono text-on-surface-variant">Kind: {c.kind}</span>
        <span className="ml-auto font-label-mono text-label-mono text-on-surface-variant">
          <span className="text-primary">+{c.additions}</span> / <span className="text-error">-{c.deletions}</span>
        </span>
      </div>

      {c.binary ? (
        <Notice icon="deployed_code" text="Binary file — no textual diff to display." />
      ) : c.status === "deleted" ? (
        <Notice icon="delete" text="File deleted in the working tree." tone="error" />
      ) : c.hunks.length === 0 ? (
        <Notice icon="check" text="No textual hunks (rename or metadata-only change)." />
      ) : (
        <div className="font-code-sm text-code-sm">
          {c.hunks.map((hunk, hi) => (
            <div key={hi}>
              <div className="flex items-center gap-space-md border-y border-outline-variant/30 bg-surface-container-low px-space-md py-space-xs font-label-mono text-label-mono text-secondary-fixed">
                <span className="text-on-surface-variant">{hunk.header || `@@ -${hunk.old_start},0 +${hunk.new_start},0 @@`}</span>
                <span className="text-on-surface-variant">Hunk {hi + 1} of {c.hunks.length}</span>
              </div>
              <div className="overflow-x-auto scroll-thin">
                {hunkRows(hunk).map((row, ri) => (
                  <DiffLine key={ri} row={row} />
                ))}
              </div>
              {hunk.truncated && (
                <div className="border-t border-outline-variant/30 bg-surface-container-lowest px-space-md py-space-xs font-label-mono text-label-mono text-on-surface-variant">
                  … hunk truncated for display (full diff via `git diff`).
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DiffLine({ row }: { row: Row }) {
  const bg = row.kind === "add" ? "bg-[var(--add-wash)]" : row.kind === "del" ? "bg-[var(--del-wash)]" : "";
  const marker = row.kind === "add" ? "+" : row.kind === "del" ? "-" : " ";
  const markerColor = row.kind === "add" ? "text-primary" : row.kind === "del" ? "text-error" : "text-transparent";
  const textColor = row.kind === "del" ? "text-on-surface-variant" : "text-on-surface";
  return (
    <div className={`flex min-w-full items-start ${bg}`}>
      <span className="w-11 shrink-0 select-none px-space-xs text-right font-code-sm text-code-sm text-outline">{row.old ?? ""}</span>
      <span className="w-11 shrink-0 select-none px-space-xs text-right font-code-sm text-code-sm text-outline">{row.neu ?? ""}</span>
      <span className={`w-4 shrink-0 select-none text-center font-code-sm text-code-sm ${markerColor}`}>{marker}</span>
      <pre className={`m-0 flex-1 whitespace-pre px-space-xs font-code-sm text-code-sm ${textColor}`}>{row.text || " "}</pre>
    </div>
  );
}

function Inspector({ report, file, onReveal }: { report: OverscopeReport; file: ScopedFile; onReveal: (p: string) => void }) {
  const meta = SCOPE[file.scope];
  const findings = findingsFor(report, file.change.path);
  const revertCmd = `git checkout -- ${file.change.path}`;
  return (
    <div className="flex flex-col gap-space-md">
      <div className="font-label-mono text-label-mono uppercase tracking-wider text-on-surface-variant">Scope Forensic Ledger</div>
      <div className={`rounded-lg p-space-md ${file.scope === "OUT_OF_SCOPE" ? "bg-error-container/20" : "bg-surface-container-lowest"}`}>
        <div className="flex items-center gap-space-sm">
          <span className={`h-2.5 w-2.5 rounded-full ${meta.dot}`} />
          <span className={`font-headline-sm text-headline-sm font-semibold uppercase ${meta.text}`}>{meta.label}</span>
        </div>
        {file.attribution_reason && <p className="mt-space-xs font-body-sm text-body-sm text-on-surface-variant">{file.attribution_reason}.</p>}
      </div>

      <div className="grid grid-cols-[auto_1fr] gap-x-space-md gap-y-space-sm font-label-mono text-label-mono">
        <span className="text-on-surface-variant">Attribution</span>
        <span className="text-on-surface">{authorLabel(file.attribution, report.agent)}</span>
        <span className="text-on-surface-variant">File Kind</span>
        <span className="text-on-surface">{file.change.kind}</span>
        <span className="text-on-surface-variant">Git State</span>
        <span className="text-on-surface">{statusLabel(file.change)} {file.change.staged ? "(index)" : "(worktree)"}</span>
      </div>

      <div className="flex flex-col gap-space-xs">
        <div className="font-label-mono text-label-mono uppercase tracking-wider text-on-surface-variant">Forensic Rationale</div>
        <ul className="flex flex-col gap-space-xs rounded-lg bg-surface-container-lowest p-space-md">
          {file.reasons.map((r, i) => (
            <li key={i} className="flex gap-space-sm font-body-sm text-body-sm text-on-surface-variant">
              <Icon name="subdirectory_arrow_right" size={13} className="mt-0.5 shrink-0 text-outline" /> {r}
            </li>
          ))}
        </ul>
      </div>

      {findings.length > 0 && (
        <div className="flex flex-col gap-space-xs">
          <div className="font-label-mono text-label-mono uppercase tracking-wider text-on-surface-variant">Active Rule Breaches ({findings.length})</div>
          {findings.map((f, i) => (
            <div key={i} className="flex flex-col gap-space-xs rounded-lg bg-surface-container-lowest p-space-md">
              <div className="flex items-center justify-between">
                <span className="font-code-sm text-code-sm font-semibold text-on-surface">{f.rule_id}</span>
                <span className={`rounded-sm px-space-sm py-0.5 font-label-mono text-label-mono font-bold uppercase ${SEVERITY[f.severity].badge}`}>{SEVERITY[f.severity].label}</span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant">{f.explanation}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-space-sm">
        <CopyButton label="Copy revert command" command={revertCmd} />
        <button
          className="app-no-drag flex items-center justify-center gap-space-sm rounded-lg bg-surface-container px-space-md py-space-sm font-code-sm text-code-sm text-on-surface transition-colors hover:bg-surface-container-high"
          onClick={() => onReveal(file.change.path)}
        >
          <Icon name="open_in_new" size={15} /> Reveal in Finder / Explorer
        </button>
        <p className="text-center font-label-mono text-label-mono text-on-surface-variant">Overscope is observation-only — it never edits your working tree.</p>
      </div>
    </div>
  );
}

function CopyButton({ label, command }: { label: string; command: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="app-no-drag flex items-center justify-between gap-space-sm rounded-lg border border-outline-variant/50 bg-surface-container-lowest px-space-md py-space-sm font-code-sm text-code-sm text-on-surface-variant transition-colors hover:bg-surface-container"
      onClick={() => {
        navigator.clipboard?.writeText(command).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1400);
        });
      }}
      title={command}
    >
      <span className="truncate">{copied ? "Copied to clipboard" : label}</span>
      <Icon name={copied ? "check" : "content_copy"} size={14} className={copied ? "text-primary" : ""} />
    </button>
  );
}

function Info({ k, val, valClass = "text-on-surface" }: { k: string; val: string; valClass?: string }) {
  return (
    <div className="flex items-center justify-between gap-space-md">
      <span className="text-on-surface-variant">{k}</span>
      <span className={valClass}>{val}</span>
    </div>
  );
}

function Notice({ icon, text, tone }: { icon: string; text: string; tone?: "error" }) {
  return (
    <div className="flex items-center gap-space-sm px-space-md py-space-lg font-code-sm text-code-sm text-on-surface-variant">
      <Icon name={icon} size={16} className={tone === "error" ? "text-error" : "text-on-surface-variant"} /> {text}
    </div>
  );
}

function Empty() {
  return (
    <div className="grid h-full place-items-center font-code-sm text-code-sm text-on-surface-variant">
      Select a file to inspect its diff.
    </div>
  );
}

function fileIcon(kind: string): string {
  const map: Record<string, string> = {
    test: "science",
    dependency: "inventory_2",
    lockfile: "lock",
    config: "settings",
    security: "shield",
    environment: "key",
    documentation: "description",
    migration: "database",
    generated: "auto_awesome",
  };
  return map[kind] ?? "code";
}
