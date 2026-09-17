from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, cast


class AgentKind(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"

class Severity(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class ScopeStatus(StrEnum):
    IN_SCOPE = "IN_SCOPE"
    ADJACENT = "ADJACENT"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNKNOWN = "UNKNOWN"

class Attribution(StrEnum):
    """Whether this working-tree change can be traced to the agent's own actions."""

    AGENT = "AGENT"
    UNATTRIBUTED = "UNATTRIBUTED"
    UNKNOWN = "UNKNOWN"

@dataclass(slots=True)
class ToolAction:
    kind: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)
    output: str | None = None
    success: bool | None = None
    timestamp: str | None = None
    provenance: str | None = None

@dataclass(slots=True)
class Session:
    id: str
    agent: AgentKind
    path: Path
    cwd: Path | None = None
    started_at: str | None = None
    updated_at: str | None = None
    user_messages: list[str] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)
    final_message: str | None = None
    tool_actions: list[ToolAction] = field(default_factory=list)
    malformed_records: int = 0
    unknown_records: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def final_response(self) -> str | None:
        if self.final_message is not None:
            return self.final_message
        if self.agent == AgentKind.CLAUDE and self.assistant_messages:
            return self.assistant_messages[-1]
        return None

@dataclass(slots=True)
class SessionCandidate:
    id: str
    agent: AgentKind
    path: Path
    modified_at: float
    score: int
    reasons: list[str] = field(default_factory=list)

@dataclass(slots=True)
class DiffHunk:
    header: str
    old_start: int | None
    new_start: int | None
    lines: list[str]

    @property
    def added_lines(self) -> list[str]:
        return [
            line[1:] for line in self.lines if line.startswith("+") and not line.startswith("+++")
        ]

    @property
    def removed_lines(self) -> list[str]:
        return [
            line[1:] for line in self.lines if line.startswith("-") and not line.startswith("---")
        ]

@dataclass(slots=True)
class FileChange:
    path: str
    status: str
    staged: bool = False
    unstaged: bool = False
    untracked: bool = False
    old_path: str | None = None
    additions: int = 0
    deletions: int = 0
    binary: bool = False
    kind: str = "source"
    hunks: list[DiffHunk] = field(default_factory=list)
    before_text: str | None = None
    after_text: str | None = None

    @property
    def added_lines(self) -> list[str]:
        return [line for hunk in self.hunks for line in hunk.added_lines]

    @property
    def removed_lines(self) -> list[str]:
        return [line for hunk in self.hunks for line in hunk.removed_lines]

@dataclass(slots=True)
class GitState:
    root: Path
    branch: str | None
    head: str | None
    changes: list[FileChange] = field(default_factory=list)

@dataclass(slots=True)
class Intent:
    text: str
    operation: str | None
    paths: list[str]
    keywords: list[str]
    constraints: list[str]
    confidence: float
    reasons: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)

@dataclass(slots=True)
class ScopedFile:
    change: FileChange
    scope: ScopeStatus
    reasons: list[str]
    attribution: Attribution = Attribution.UNKNOWN
    attribution_reason: str | None = None

@dataclass(slots=True)
class Finding:
    rule_id: str
    title: str
    severity: Severity
    explanation: str
    evidence: str
    remediation: str
    path: str | None = None
    line: int | None = None

@dataclass(slots=True)
class Reconciliation:
    claim: str
    status: str
    explanation: str
    evidence: str | None = None

@dataclass(slots=True)
class OverscopeReport:
    schema_version: str
    generated_at: str
    repository: str
    branch: str | None
    head: str | None
    agent: str
    session_id: str
    session_path: str
    intent: Intent
    files: list[ScopedFile]
    findings: list[Finding]
    reconciliations: list[Reconciliation]
    review_first: list[str]
    summary: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = cast(dict[str, Any], _jsonable(asdict(self)))
        raw_files = payload.get("files")
        if isinstance(raw_files, list):
            for raw_file in raw_files:
                if not isinstance(raw_file, dict):
                    continue
                change = raw_file.get("change")
                if not isinstance(change, dict):
                    continue
                change.pop("before_text", None)
                change.pop("after_text", None)
                hunks = change.get("hunks")
                if not isinstance(hunks, list):
                    continue
                for hunk in hunks:
                    if not isinstance(hunk, dict):
                        continue
                    lines = hunk.get("lines")
                    if isinstance(lines, list) and len(lines) > 80:
                        hunk["lines"] = lines[:80]
                        hunk["truncated"] = True
        return payload

def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
