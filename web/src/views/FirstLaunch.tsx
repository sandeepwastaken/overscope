import { Logo } from "../Logo";
import { Icon } from "../ui";

export function FirstLaunch({
  busy,
  error,
  hasRepository,
  onOpen,
  onChooseSession,
}: {
  busy: boolean;
  error: string | null;
  hasRepository: boolean;
  onOpen: () => void;
  onChooseSession: () => void;
}) {
  const recent = (() => {
    const r = localStorage.getItem("overscope.repository");
    return r ? r.split("/").slice(-3).join("/") : null;
  })();

  return (
    <div
      className="flex h-full min-w-[760px] flex-col bg-surface"
      style={{ backgroundImage: "radial-gradient(circle at 50% 22%, rgb(var(--primary) / 0.07), transparent 42%)" }}
    >
      <header className="app-drag flex h-13 shrink-0 items-center gap-space-md border-b border-outline-variant/40 bg-surface-container-lowest px-space-md py-space-md">
        <div className="flex items-center gap-space-xs">
          {["#ff5f56", "#ffbd2e", "#27c93f"].map((c) => (
            <span key={c} className="inline-block h-3 w-3 rounded-full opacity-80" style={{ background: c }} />
          ))}
        </div>
        <span className="font-label-mono text-label-mono uppercase tracking-[0.12em] text-on-surface-variant">Workspace // Idle</span>
        <div className="ml-auto flex items-center gap-space-sm font-label-mono text-label-mono">
          <span className="flex items-center gap-space-xs rounded bg-surface-container px-space-md py-space-xs text-on-surface-variant">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" /> DAEMON v0.1.0
          </span>
          <span className="rounded bg-surface-container-high px-space-md py-space-xs uppercase tracking-wider text-on-surface-variant">Offline Airgap</span>
        </div>
      </header>

      <main className="scroll-thin flex flex-1 items-start justify-center overflow-y-auto px-space-xl py-space-xl">
        <div className="flex w-full max-w-[640px] flex-col items-center pb-space-xl pt-10 text-center">
          <div className="mb-space-lg" style={{ filter: "drop-shadow(0 0 26px rgb(var(--primary) / 0.16))" }}>
            <Logo size={64} />
          </div>
          <div className="mb-space-md flex items-center gap-space-xs rounded bg-surface-container px-space-md py-space-xs font-label-mono text-label-mono uppercase tracking-[0.1em] text-primary">
            <Icon name="shield" size={13} /> Forensic Pre-Commit Engine
          </div>
          <h1 className="font-headline-lg text-[30px] leading-[36px] tracking-[-0.025em] text-on-surface">
            Know what changed. <span className="text-primary">Know why.</span>
          </h1>
          <p className="mt-space-md max-w-[560px] font-body-lg text-body-lg leading-relaxed text-on-surface-variant">
            Deterministic pre-commit auditing for Claude Code, Codex, and autonomous CLI agents. Inspect scope drift, verify
            agent claims against git truth, and catch unrequested modifications.
          </p>

          <div className="mt-space-xl w-full rounded-lg border border-outline-variant/40 bg-surface-container-lowest p-space-lg">
            <div className="flex items-center justify-between font-label-mono text-label-mono uppercase tracking-wider">
              <span className="flex items-center gap-space-xs text-on-surface-variant">
                <Icon name="query_stats" size={13} className="text-primary" /> Sample Agent Drift Ratio
              </span>
              <span className="text-primary">89.4% Verified</span>
            </div>
            <div className="my-space-md flex h-2 gap-[2px] overflow-hidden rounded-sm">
              <span className="bg-primary" style={{ width: "74%" }} />
              <span className="bg-secondary-container" style={{ width: "15%" }} />
              <span className="bg-error" style={{ width: "11%" }} />
            </div>
            <div className="flex items-center justify-between font-label-mono text-label-mono">
              <span className="flex items-center gap-space-xs text-on-surface-variant"><span className="h-1.5 w-1.5 rounded-full bg-primary" /> 74% In-Scope</span>
              <span className="flex items-center gap-space-xs text-on-surface-variant"><span className="h-1.5 w-1.5 rounded-full bg-secondary-container" /> 15% Dependent</span>
              <span className="flex items-center gap-space-xs text-on-surface-variant"><span className="h-1.5 w-1.5 rounded-full bg-error" /> 11% Outlier Drift</span>
            </div>
          </div>

          <div className="mt-space-lg flex w-full items-stretch gap-space-sm">
            <button
              className="app-no-drag flex flex-1 items-center justify-center gap-space-md rounded-lg bg-primary px-space-lg py-space-md font-headline-sm text-headline-sm font-bold text-on-primary transition-colors hover:bg-primary-fixed disabled:opacity-60"
              onClick={onOpen}
              disabled={busy}
            >
              {busy ? <Icon name="progress_activity" size={18} className="animate-spin" /> : <Icon name="folder_open" size={18} />}
              {busy ? "Analyzing…" : "Open Git Repository…"}
              <kbd className="rounded bg-black/15 px-space-sm py-0.5 font-label-mono text-label-mono">⌘O</kbd>
            </button>
            {hasRepository && (
              <button
                className="app-no-drag flex items-center gap-space-xs rounded-lg border border-outline-variant/50 bg-surface-container px-space-md font-code-sm text-code-sm text-on-surface-variant transition-colors hover:bg-surface-container-high"
                onClick={onChooseSession}
                title="Pair this repository with a specific agent transcript"
              >
                <Icon name="history" size={15} /> Session…
              </button>
            )}
          </div>

          <div className="mt-space-xl w-full text-left">
            <div className="flex items-center justify-between px-space-xs font-label-mono text-label-mono uppercase tracking-wider text-on-surface-variant">
              <span className="flex items-center gap-space-xs"><Icon name="data_object" size={13} /> Audited Repositories</span>
              <span>{recent ? "1 recent" : "None yet"}</span>
            </div>
            {recent ? (
              <button
                className="app-no-drag mt-space-sm flex w-full items-center gap-space-md rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-space-md py-space-md transition-colors hover:bg-surface-container"
                onClick={onOpen}
              >
                <span className="grid h-8 w-8 place-items-center rounded bg-surface-container text-on-surface-variant"><Icon name="terminal" size={16} /></span>
                <span className="flex flex-1 flex-col">
                  <span className="font-code-sm text-code-sm text-on-surface">{recent}</span>
                  <span className="font-label-mono text-label-mono text-on-surface-variant">last audited locally</span>
                </span>
                <span className="flex items-center gap-space-xs font-label-mono text-label-mono uppercase text-primary">Audit <Icon name="arrow_forward" size={14} /></span>
              </button>
            ) : (
              <p className="mt-space-sm rounded-lg border border-dashed border-outline-variant/50 px-space-md py-space-lg text-center font-code-sm text-code-sm text-on-surface-variant">
                Open a local Git repository to begin. Overscope pairs it with the most recent Claude Code or Codex session.
              </p>
            )}
          </div>

          {error && (
            <div className="mt-space-md flex w-full items-center gap-space-md rounded-lg border border-error/60 bg-error-container/30 p-space-md text-left">
              <Icon name="error" size={16} className="text-error" />
              <span className="flex-1 font-code-sm text-code-sm text-on-error-container">{error}</span>
              <button className="app-no-drag rounded border border-error/60 px-space-md py-space-xs font-label-mono text-label-mono uppercase text-error" onClick={onChooseSession}>Choose transcript…</button>
            </div>
          )}

          <div className="mt-space-xl flex items-center gap-space-xs font-label-mono text-label-mono uppercase tracking-wider text-on-surface-variant">
            <Icon name="lock" size={13} className="text-primary" /> 100% Local Analysis · No Account · No Telemetry
          </div>
        </div>
      </main>
    </div>
  );
}
