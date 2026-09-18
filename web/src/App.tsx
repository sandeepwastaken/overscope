import { useCallback, useEffect, useState } from "react";

import {
  DEMO_REPOSITORY,
  analyzeRepository,
  getRepositoryStatus,
  isDesktop,
  revealFile,
  runGitAction,
  selectRepository,
  selectSession,
} from "./bridge";
import type { GitAction, RepositoryStatus } from "./bridge";
import {
  SCOPE,
  agentDisplay,
  relativeTime,
  sortedFiles,
  totals,
} from "./lib";
import { Logo } from "./Logo";
import { Icon } from "./ui";
import type { OverscopeReport } from "./types";
import { FirstLaunch } from "./views/FirstLaunch";
import { Situation } from "./views/Situation";
import { DiffInspector } from "./views/DiffInspector";
import { Claims } from "./views/Claims";
import { Evidence } from "./views/Evidence";

export type View = "overview" | "changes" | "claims" | "evidence";
type Theme = "dark" | "light";

const NAV: { id: View; label: string; icon: string }[] = [
  { id: "overview", label: "Situation", icon: "dashboard" },
  { id: "changes", label: "Changes", icon: "difference" },
  { id: "claims", label: "Claims", icon: "fact_check" },
  { id: "evidence", label: "Evidence", icon: "terminal" },
];

const alertCount = (r: OverscopeReport) =>
  r.findings.filter((f) => f.severity === "HIGH" || f.severity === "MEDIUM").length;
const mismatchCount = (r: OverscopeReport) => r.reconciliations.filter((x) => x.status === "MISMATCH").length;

export function App() {
  const [report, setReport] = useState<OverscopeReport | null>(null);
  const [repository, setRepository] = useState(() => localStorage.getItem("overscope.repository") ?? "");
  const [status, setStatus] = useState<RepositoryStatus | null>(null);
  const [view, setView] = useState<View>("overview");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [gitBusy, setGitBusy] = useState<GitAction | null>(null);
  const [message, setMessage] = useState<{ tone: "error" | "ok"; text: string } | null>(null);
  const [theme, setTheme] = useState<Theme>(() =>
    localStorage.getItem("overscope.theme") === "light" ? "light" : "dark",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("overscope.theme", theme);
  }, [theme]);

  const run = useCallback(async (path: string, session?: string | null) => {
    if (!path) return;
    setRepository(path);
    setBusy(true);
    setMessage(null);
    try {
      const next = await analyzeRepository({ repository: path, session });
      setReport(next);
      setRepository(next.repository);
      localStorage.setItem("overscope.repository", next.repository);
      setSelectedPath((current) =>
        current && next.files.some((f) => f.change.path === current)
          ? current
          : next.review_first[0] ?? next.files[0]?.change.path ?? null,
      );
      try {
        setStatus(await getRepositoryStatus(next.repository));
      } catch (reason) {
        setStatus(null);
        setMessage({ tone: "error", text: `Git status unavailable: ${String(reason)}` });
      }
    } catch (reason) {
      setReport(null);
      setMessage({ tone: "error", text: reason instanceof Error ? reason.message : String(reason) });
    } finally {
      setBusy(false);
    }
  }, []);

  const choose = useCallback(async () => {
    if (!isDesktop()) {
      await run(DEMO_REPOSITORY);
      return;
    }
    const picked = await selectRepository();
    if (picked) await run(picked);
  }, [run]);

  const chooseSession = useCallback(async () => {
    if (!repository || !isDesktop()) return;
    const picked = await selectSession();
    if (picked) await run(repository, picked);
  }, [repository, run]);

  const performGitAction = useCallback(
    async (action: GitAction) => {
      if (!repository || !status?.remote) return;
      if (action === "push" && !window.confirm(`Push local commits to ${status.remote.name} using your existing ${status.remote.transport} credentials?`)) return;
      if (action === "pull" && !window.confirm(`Fast-forward this branch from ${status.upstream ?? status.remote.name}? This updates local files.`)) return;
      setGitBusy(action);
      setMessage(null);
      try {
        const result = await runGitAction(repository, action);
        setStatus(result.status);
        setMessage({ tone: "ok", text: `${result.message}. ${result.output}` });
        if (action === "pull") await run(repository);
      } catch (reason) {
        setMessage({ tone: "error", text: reason instanceof Error ? reason.message : String(reason) });
      } finally {
        setGitBusy(null);
      }
    },
    [repository, run, status],
  );

  useEffect(() => {
    if (repository && isDesktop()) void run(repository);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const command = event.metaKey || event.ctrlKey;
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (command && event.key.toLowerCase() === "o") {
        event.preventDefault();
        void choose();
      } else if (command && event.key.toLowerCase() === "r") {
        event.preventDefault();
        if (repository) void run(repository);
      } else if (command && /^[1-4]$/.test(event.key)) {
        event.preventDefault();
        setView(NAV[Number(event.key) - 1].id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [choose, repository, run]);

  const inspect = useCallback((path: string) => {
    setSelectedPath(path);
    setView("changes");
  }, []);

  if (!report) {
    return (
      <FirstLaunch
        busy={busy}
        error={message?.tone === "error" ? message.text : null}
        hasRepository={Boolean(repository)}
        onOpen={choose}
        onChooseSession={chooseSession}
      />
    );
  }

  return (
    <div className="h-full min-w-[980px] bg-surface text-on-surface">
      <TopBar
        report={report}
        status={status}
        theme={theme}
        busy={busy}
        onOpen={choose}
        onRescan={() => repository && run(repository)}
        onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
      />
      <Sidebar
        report={report}
        view={view}
        selectedPath={selectedPath}
        theme={theme}
        onView={setView}
        onFile={inspect}
        onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        alertCount={alertCount(report)}
        mismatchCount={mismatchCount(report)}
      />
      <main className="fixed left-72 right-0 top-14 bottom-0 overflow-y-auto bg-surface scroll-thin">
        {message && (
          <div
            className={`mx-gutter mt-space-md flex items-center gap-space-sm rounded-lg px-space-md py-space-sm font-code-sm text-code-sm ${
              message.tone === "error"
                ? "bg-error-container/40 text-on-error-container"
                : "bg-primary/10 text-primary"
            }`}
          >
            <Icon name={message.tone === "error" ? "error" : "check_circle"} size={15} />
            <span className="truncate">{message.text}</span>
            <button className="app-no-drag ml-auto shrink-0 opacity-70 hover:opacity-100" onClick={() => setMessage(null)}>
              <Icon name="close" size={14} />
            </button>
          </div>
        )}
        {view === "overview" && <Situation report={report} status={status} gitBusy={gitBusy} onGitAction={performGitAction} onInspect={inspect} />}
        {view === "changes" && <DiffInspector report={report} selectedPath={selectedPath} onSelect={setSelectedPath} onReveal={(p) => void revealFile(report.repository, p)} />}
        {view === "claims" && <Claims report={report} onInspect={inspect} />}
        {view === "evidence" && <Evidence report={report} onInspect={inspect} />}
      </main>
    </div>
  );
}

function TopBar({
  report,
  status,
  theme,
  busy,
  onOpen,
  onRescan,
  onToggleTheme,
}: {
  report: OverscopeReport;
  status: RepositoryStatus | null;
  theme: Theme;
  busy: boolean;
  onOpen: () => void;
  onRescan: () => void;
  onToggleTheme: () => void;
}) {
  const repoName = report.repository.split("/").slice(-2).join("/");
  const branch = status?.branch ?? report.branch ?? "detached";
  return (
    <header className="app-drag fixed left-0 right-0 top-0 z-50 flex h-14 select-none items-center justify-between border-b border-outline-variant/40 bg-surface-container-lowest/95 pl-[80px] pr-space-md backdrop-blur-md">
      <div className="flex items-center gap-space-md">
        <div className="flex items-center gap-space-sm">
          <Logo size={30} />
          <span className="font-headline-sm text-headline-sm tracking-[0.18em] text-on-surface">OVERSCOPE</span>
        </div>
        <div className="mx-space-xs h-4 w-px bg-surface-container-highest" />
        <button
          className="app-no-drag flex items-center gap-space-sm rounded-lg bg-surface-container-low px-space-md py-space-xs transition-colors hover:bg-surface-container"
          onClick={onOpen}
          title="Open a different repository (⌘O)"
        >
          <Icon name="source" size={16} className="text-on-surface-variant" />
          <span className="font-code-sm text-code-sm text-on-surface">{repoName}</span>
          <span className="font-code-sm text-code-sm text-on-surface-variant">:</span>
          <span className="flex items-center gap-space-xs font-code-sm text-code-sm text-primary">
            <Icon name="fork_right" size={14} />
            {branch}
          </span>
          <Icon name="unfold_more" size={16} className="text-on-surface-variant" />
        </button>
        <div className="app-no-drag flex items-center gap-space-xs rounded-lg bg-surface-container px-space-md py-space-xs">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
          </span>
          <span className="font-code-sm text-code-sm text-on-surface">{agentDisplay(report.agent)}</span>
        </div>
        <div className="flex items-center gap-space-xs font-label-ui text-label-ui text-on-surface-variant">
          <Icon name="history" size={14} />
          <span>Scanned {relativeTime(report.generated_at)}</span>
        </div>
      </div>
      <div className="flex items-center gap-space-md">
        <div className="app-no-drag flex items-center gap-space-xs rounded-lg bg-surface-container-low px-space-md py-space-xs font-label-mono text-label-mono text-on-surface-variant">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
          <span>Local only (0 telemetries)</span>
        </div>
        <div className="flex items-center gap-space-sm">
          <button
            className="app-no-drag flex items-center gap-space-xs rounded-lg bg-surface-container px-space-md py-space-xs font-code-sm text-code-sm text-on-surface transition-colors hover:bg-surface-container-high disabled:opacity-50"
            onClick={onRescan}
            disabled={busy}
          >
            {busy ? <Icon name="progress_activity" size={14} className="animate-spin text-primary" /> : <span className="font-headline-sm text-headline-sm text-primary">⌘R</span>}
            <span>Rescan</span>
          </button>
          <button
            className="app-no-drag flex items-center gap-space-xs rounded-lg bg-surface-container px-space-md py-space-xs font-code-sm text-code-sm text-on-surface transition-colors hover:bg-surface-container-high"
            onClick={onOpen}
          >
            <span className="font-headline-sm text-headline-sm text-on-surface-variant">⌘O</span>
            <span>Open Repo</span>
          </button>
        </div>
        <button
          className="app-no-drag flex h-8 w-8 items-center justify-center rounded-full bg-primary text-on-primary"
          onClick={onToggleTheme}
          title="Toggle theme"
        >
          <Icon name={theme === "dark" ? "dark_mode" : "light_mode"} size={18} />
        </button>
      </div>
    </header>
  );
}

function Sidebar({
  report,
  view,
  selectedPath,
  theme,
  onView,
  onFile,
  onToggleTheme,
  alertCount,
  mismatchCount,
}: {
  report: OverscopeReport;
  view: View;
  selectedPath: string | null;
  theme: Theme;
  onView: (v: View) => void;
  onFile: (path: string) => void;
  onToggleTheme: () => void;
  alertCount: number;
  mismatchCount: number;
}) {
  const { additions, deletions } = totals(report);
  const badge = (id: View) => {
    if (id === "overview")
      return alertCount ? { text: `${alertCount} alert${alertCount === 1 ? "" : "s"}`, cls: "bg-error-container text-on-error-container" } : { text: "clear", cls: "bg-surface-container text-on-surface-variant" };
    if (id === "changes") return { text: `${report.files.length} files, +${additions} -${deletions}`, cls: "bg-surface-container text-on-surface-variant" };
    if (id === "claims") return mismatchCount ? { text: `${mismatchCount} mismatch${mismatchCount === 1 ? "" : "es"}`, cls: "bg-tertiary-container text-on-tertiary-container" } : { text: `${report.reconciliations.length} claims`, cls: "bg-surface-container text-on-surface-variant" };
    return { text: "JSON / Rules", cls: "bg-surface-container text-on-surface-variant" };
  };
  return (
    <aside className="fixed bottom-0 left-0 top-14 z-40 flex w-72 select-none flex-col justify-between border-r border-outline-variant/40 bg-surface-container-low">
      <div className="scroll-thin flex flex-1 flex-col gap-space-lg overflow-y-auto px-space-md py-space-md">
        <div className="flex flex-col gap-space-xs">
          <div className="px-space-sm font-label-mono text-label-mono uppercase tracking-wider text-on-surface-variant">Forensic Ledger</div>
          <nav className="flex flex-col gap-space-xs">
            {NAV.map((item) => {
              const active = view === item.id;
              const b = badge(item.id);
              return (
                <button
                  key={item.id}
                  aria-current={active ? "page" : undefined}
                  onClick={() => onView(item.id)}
                  className={`flex items-center justify-between rounded-lg px-space-md py-space-sm transition-colors ${
                    active ? "bg-surface-container-high font-semibold text-primary" : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                  }`}
                >
                  <span className="flex items-center gap-space-md font-headline-sm text-headline-sm">
                    <Icon name={item.icon} size={18} />
                    <span>{item.label}</span>
                  </span>
                  <span className={`rounded font-code-sm text-code-sm px-space-sm py-0.5 ${b.cls}`}>{b.text}</span>
                </button>
              );
            })}
          </nav>
        </div>

        <div className="flex flex-col gap-space-xs">
          <div className="flex items-center justify-between px-space-sm">
            <span className="font-label-mono text-label-mono uppercase tracking-wider text-on-surface-variant">Changed Files</span>
            <span className="font-code-sm text-code-sm text-on-surface-variant">{report.files.length} modified</span>
          </div>
          <div className="flex flex-col gap-space-xs font-code-sm text-code-sm">
            {report.files.length === 0 && <div className="px-space-md py-space-sm text-on-surface-variant">Working tree clean</div>}
            {sortedFiles(report.files).map((file) => {
              const meta = SCOPE[file.scope];
              const active = selectedPath === file.change.path;
              return (
                <button
                  key={file.change.path}
                  onClick={() => onFile(file.change.path)}
                  className={`group flex items-center justify-between rounded-lg px-space-md py-space-sm text-left transition-colors ${active ? "bg-surface-container" : "hover:bg-surface-container"}`}
                >
                  <span className="flex items-center gap-space-sm overflow-hidden">
                    <span className={`h-2 w-2 shrink-0 rounded-full ${meta.dot}`} />
                    <span className={`truncate ${file.scope === "OUT_OF_SCOPE" ? "text-error" : "text-on-surface"}`}>{file.change.path}</span>
                  </span>
                  <span className={`ml-space-sm shrink-0 font-label-mono text-label-mono uppercase ${meta.text}`}>{meta.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-space-sm bg-surface-container-lowest p-space-md">
        <div className="flex items-center justify-between font-label-mono text-label-mono text-on-surface-variant">
          <span>v0.1.0 • Engine: overscope</span>
          <button className="transition-colors hover:text-on-surface" onClick={onToggleTheme} title="Toggle theme">
            <Icon name={theme === "dark" ? "dark_mode" : "light_mode"} size={16} />
          </button>
        </div>
        <div className="flex items-center gap-space-xs font-label-mono text-label-mono text-on-surface-variant">
          <Icon name="lock" size={12} className="text-primary" />
          <span>Privacy: 100% Local</span>
        </div>
      </div>
    </aside>
  );
}
