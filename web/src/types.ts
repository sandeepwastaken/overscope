// Mirrors src/overscope/models.py — the stable `overscope --json` schema (schema_version 1.0).

export type Severity = "HIGH" | "MEDIUM" | "LOW" | "INFO";
export type ScopeStatus = "IN_SCOPE" | "ADJACENT" | "OUT_OF_SCOPE" | "UNKNOWN";
export type Attribution = "AGENT" | "UNATTRIBUTED" | "UNKNOWN";

export interface DiffHunk {
  header: string;
  old_start: number | null;
  new_start: number | null;
  lines: string[];
  truncated?: boolean;
}

export interface FileChange {
  path: string;
  status: string;
  staged: boolean;
  unstaged: boolean;
  untracked: boolean;
  old_path: string | null;
  additions: number;
  deletions: number;
  binary: boolean;
  kind: string;
  hunks: DiffHunk[];
}

export interface ScopedFile {
  change: FileChange;
  scope: ScopeStatus;
  reasons: string[];
  attribution: Attribution;
  attribution_reason: string | null;
}

export interface Finding {
  rule_id: string;
  title: string;
  severity: Severity;
  explanation: string;
  evidence: string;
  remediation: string;
  path: string | null;
  line: number | null;
}

export interface Reconciliation {
  claim: string;
  status: string;
  explanation: string;
  evidence: string | null;
}

export interface Intent {
  text: string;
  operation: string | null;
  paths: string[];
  keywords: string[];
  constraints: string[];
  confidence: number;
  reasons: string[];
  avoid: string[];
}

export interface OverscopeReport {
  schema_version: string;
  generated_at: string;
  repository: string;
  branch: string | null;
  head: string | null;
  agent: string;
  session_id: string;
  session_path: string;
  intent: Intent;
  files: ScopedFile[];
  findings: Finding[];
  reconciliations: Reconciliation[];
  review_first: string[];
  summary: string;
  warnings: string[];
}

export interface ReportError {
  error: { message: string; type: string };
  schema_version: string;
}
