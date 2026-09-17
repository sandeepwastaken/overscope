import { invoke } from "@tauri-apps/api/core";

import sample from "./sample.json";
import type { OverscopeReport } from "./types";

export const DEMO_REPOSITORY = (sample as OverscopeReport).repository;

export interface AnalyzeRequest {
  repository: string;
  session?: string | null;
  agent?: "claude" | "codex" | null;
}

export interface GitRemote {
  name: string;
  url: string;
  provider: string;
  transport: string;
}

export interface RepositoryStatus {
  repository: string;
  branch: string | null;
  head: string | null;
  dirty: boolean;
  changedFiles: number;
  stagedFiles: number;
  untrackedFiles: number;
  remote: GitRemote | null;
  upstream: string | null;
  ahead: number;
  behind: number;
}

export type GitAction = "fetch" | "pull" | "push";

export interface GitActionResult {
  message: string;
  output: string;
  status: RepositoryStatus;
}

export function isDesktop(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

export async function selectRepository(): Promise<string | null> {
  if (!isDesktop()) return null;
  return invoke<string | null>("select_repository");
}

export async function selectSession(): Promise<string | null> {
  if (!isDesktop()) return null;
  return invoke<string | null>("select_session");
}

export async function analyzeRepository(request: AnalyzeRequest): Promise<OverscopeReport> {
  if (!isDesktop()) {
    await new Promise((resolve) => window.setTimeout(resolve, 450));
    return sample as OverscopeReport;
  }
  return invoke<OverscopeReport>("analyze_repository", { request });
}

export async function getRepositoryStatus(repository: string): Promise<RepositoryStatus> {
  if (!isDesktop()) {
    return {
      repository,
      branch: "main",
      head: "7f81b94d21",
      dirty: true,
      changedFiles: 7,
      stagedFiles: 2,
      untrackedFiles: 1,
      remote: {
        name: "origin",
        url: "git@github.com:acme/web-api.git",
        provider: "GitHub",
        transport: "SSH",
      },
      upstream: "origin/main",
      ahead: 2,
      behind: 0,
    };
  }
  return invoke<RepositoryStatus>("repository_status", { repository });
}

export async function runGitAction(repository: string, action: GitAction): Promise<GitActionResult> {
  if (!isDesktop()) {
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    const status = await getRepositoryStatus(repository);
    return {
      message: `${action[0].toUpperCase()}${action.slice(1)} preview completed`,
      output: "Preview mode does not contact a remote.",
      status: action === "push" ? { ...status, ahead: 0 } : status,
    };
  }
  return invoke<GitActionResult>("run_git_action", { repository, action });
}

export async function revealFile(repository: string, relativePath: string): Promise<void> {
  if (!isDesktop()) return;
  await invoke("reveal_file", { repository, relativePath });
}
