import type { Attribution, Finding, ScopeStatus, ScopedFile, Severity, OverscopeReport } from "./types";

export interface ScopeMeta {
  label: string;
  text: string;
  dot: string;
  bar: string;
}

export const SCOPE: Record<ScopeStatus, ScopeMeta> = {
  IN_SCOPE: { label: "In Scope", text: "text-primary", dot: "bg-primary", bar: "bg-primary" },
  ADJACENT: {
    label: "Adjacent",
    text: "text-secondary-fixed",
    dot: "bg-secondary-container",
    bar: "bg-secondary-container",
  },
  OUT_OF_SCOPE: { label: "Out of Scope", text: "text-error", dot: "bg-error-container", bar: "bg-error" },
  UNKNOWN: { label: "Unknown", text: "text-on-surface-variant", dot: "bg-outline", bar: "bg-outline/60" },
};

export interface SevMeta {
  label: string;
  text: string;
  badge: string;
  rail: string;
}

export const SEVERITY: Record<Severity, SevMeta> = {
  HIGH: {
    label: "High",
    text: "text-error",
    badge: "bg-error-container text-on-error-container",
    rail: "bg-error",
  },
  MEDIUM: {
    label: "Medium",
    text: "text-tertiary",
    badge: "bg-tertiary-container/25 text-tertiary",
    rail: "bg-tertiary-container",
  },
  LOW: {
    label: "Low",
    text: "text-secondary-fixed",
    badge: "bg-secondary-container/20 text-secondary-fixed",
    rail: "bg-secondary-container",
  },
  INFO: {
    label: "Info",
    text: "text-on-surface-variant",
    badge: "bg-surface-container-high text-on-surface-variant",
    rail: "bg-outline",
  },
};

export interface StatusMeta {
  label: string;
  icon: string;
  text: string;
  badge: string;
}

export function statusMeta(status: string): StatusMeta {
  switch (status) {
    case "SUPPORTED":
      return { label: "Supported", icon: "verified", text: "text-primary", badge: "bg-primary/15 text-primary" };
    case "MISMATCH":
      return {
        label: "Mismatch",
        icon: "gpp_bad",
        text: "text-error",
        badge: "bg-error-container text-on-error-container",
      };
    case "UNVERIFIED":
      return {
        label: "Unverified",
        icon: "warning",
        text: "text-tertiary",
        badge: "bg-tertiary-container/25 text-tertiary",
      };
    default:
      return {
        label: "Insufficient Evidence",
        icon: "help",
        text: "text-on-surface-variant",
        badge: "bg-surface-container-high text-on-surface-variant",
      };
  }
}

const SEV_RANK: Record<Severity, number> = { HIGH: 0, MEDIUM: 1, LOW: 2, INFO: 3 };
export const SEVERITY_ORDER: Severity[] = ["HIGH", "MEDIUM", "LOW", "INFO"];
export const SCOPE_BAR_ORDER: ScopeStatus[] = ["IN_SCOPE", "ADJACENT", "UNKNOWN", "OUT_OF_SCOPE"];
export const SCOPE_TABLE_ORDER: ScopeStatus[] = ["OUT_OF_SCOPE", "UNKNOWN", "ADJACENT", "IN_SCOPE"];

export interface Verdict {
  label: string;
  tone: "clean" | "review" | "breach";
  text: string;
  badge: string;
  icon: string;
}

export function verdict(report: OverscopeReport): Verdict {
  const highs = report.findings.filter((f) => f.severity === "HIGH").length;
  const meds = report.findings.filter((f) => f.severity === "MEDIUM").length;
  const out = report.files.filter((f) => f.scope === "OUT_OF_SCOPE").length;
  if (report.files.length === 0)
    return { label: "Clean Tree", tone: "clean", text: "text-primary", badge: "bg-primary/15 text-primary", icon: "verified" };
  if (highs)
    return { label: "Review Suggested", tone: "breach", text: "text-error", badge: "bg-error-container text-on-error-container", icon: "warning" };
  if (meds || out)
    return { label: "Review Suggested", tone: "review", text: "text-tertiary", badge: "bg-tertiary-container/25 text-tertiary", icon: "warning" };
  return { label: "Looks Clean", tone: "clean", text: "text-primary", badge: "bg-primary/15 text-primary", icon: "verified" };
}

export function riskScore(report: OverscopeReport): number {
  let score = 0;
  for (const f of report.findings) score += { HIGH: 34, MEDIUM: 12, LOW: 4, INFO: 1 }[f.severity];
  score += report.files.filter((f) => f.scope === "OUT_OF_SCOPE").length * 14;
  score += report.reconciliations.filter((r) => r.status === "MISMATCH").length * 10;
  return Math.max(0, Math.min(100, Math.round(score)));
}

export function driftLabel(score: number): string {
  if (score >= 65) return "High Drift";
  if (score >= 35) return "Moderate Drift";
  if (score > 0) return "Low Drift";
  return "No Drift";
}

export function agentDisplay(agent: string): string {
  if (agent === "claude") return "Claude Code";
  if (agent === "codex") return "OpenAI Codex";
  return agent.charAt(0).toUpperCase() + agent.slice(1);
}

export function authorLabel(attribution: Attribution, agent: string): string {
  if (attribution === "AGENT") return agentDisplay(agent);
  if (attribution === "UNATTRIBUTED") return "Developer (local)";
  return "Unattributed";
}

export interface ScopeCount {
  status: ScopeStatus;
  count: number;
  pct: number;
}

export function scopeDistribution(report: OverscopeReport): ScopeCount[] {
  const total = report.files.length || 1;
  return SCOPE_BAR_ORDER.map((status) => {
    const count = report.files.filter((f) => f.scope === status).length;
    return { status, count, pct: Math.round((count / total) * 100) };
  });
}

export function severityCounts(findings: Finding[]): [Severity, number][] {
  return SEVERITY_ORDER.map((s) => [s, findings.filter((f) => f.severity === s).length] as [Severity, number]);
}

export function totals(report: OverscopeReport): { additions: number; deletions: number } {
  return report.files.reduce(
    (acc, f) => ({ additions: acc.additions + f.change.additions, deletions: acc.deletions + f.change.deletions }),
    { additions: 0, deletions: 0 },
  );
}

export function sortedFiles(files: ScopedFile[]): ScopedFile[] {
  return [...files].sort((a, b) => {
    const d = SCOPE_TABLE_ORDER.indexOf(a.scope) - SCOPE_TABLE_ORDER.indexOf(b.scope);
    return d !== 0 ? d : a.change.path.localeCompare(b.change.path);
  });
}

export function findingsFor(report: OverscopeReport, path: string): Finding[] {
  return report.findings.filter((f) => f.path === path).sort((a, b) => SEV_RANK[a.severity] - SEV_RANK[b.severity]);
}

export function worstFinding(report: OverscopeReport, path: string): Finding | undefined {
  return findingsFor(report, path)[0];
}

export function statusLabel(change: ScopedFile["change"]): string {
  if (change.staged && !change.unstaged) return "staged";
  if (change.untracked) return "untracked";
  return "unstaged";
}

export function baseName(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const s = Math.max(0, (Date.now() - then) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
