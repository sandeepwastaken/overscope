from __future__ import annotations

import json
import re
import tomllib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import PurePosixPath

from overscope.config import Config
from overscope.models import Finding, Intent, ScopedFile, ScopeStatus, Session, Severity
from overscope.sessions.base import shell_commands


@dataclass(slots=True)
class RuleContext:
    files: list[ScopedFile]
    intent: Intent
    session: Session
    config: Config

class Rule(ABC):
    id: str
    title: str
    severity: Severity
    description: str

    @abstractmethod
    def check(self, context: RuleContext) -> list[Finding]: ...

    def finding(
        self,
        explanation: str,
        evidence: str,
        remediation: str,
        *,
        path: str | None = None,
        line: int | None = None,
        severity: Severity | None = None,
    ) -> Finding:
        return Finding(
            self.id,
            self.title,
            severity or self.severity,
            explanation,
            evidence,
            remediation,
            path,
            line,
        )

class DeletedTestRule(Rule):
    id = "tests.deleted"
    title = "Test coverage deleted"
    severity = Severity.HIGH
    description = "Flags deleted test files or substantial removed test code."

    def check(self, context: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for item in context.files:
            change = item.change
            if change.kind == "test" and change.status == "deleted":
                findings.append(
                    self.finding(
                        "A test file was deleted.",
                        change.path,
                        "Confirm the covered behavior remains tested.",
                        path=change.path,
                    )
                )
            elif (
                change.kind == "test"
                and change.deletions >= 10
                and change.deletions > change.additions * 2
            ):
                findings.append(
                    self.finding(
                        "Substantially more test code was removed than added.",
                        f"-{change.deletions} +{change.additions}",
                        "Review removed cases for lost coverage.",
                        path=change.path,
                        severity=Severity.MEDIUM,
                    )
                )
        return findings

class DisabledTestRule(Rule):
    id = "tests.disabled"
    title = "Test disabled or skipped"
    severity = Severity.MEDIUM
    description = "Detects newly added skip, xfail, pending, and disabled-test markers."
    pattern = re.compile(
        r"(?:pytest\.mark\.(?:skip|xfail)|\b(?:describe|it|test)\.skip\b|\bxit\s*\(|\bxdescribe\s*\(|@unittest\.skip|\bpending\s*\()",
        re.I,
    )

    def check(self, context: RuleContext) -> list[Finding]:
        return _added_line_findings(
            self,
            context,
            self.pattern,
            "A newly added line disables or skips a test.",
            "Verify the skip is intentional and time-bounded.",
        )

class WeakenedAssertionRule(Rule):
    id = "tests.assertion_weakened"
    title = "Assertion may be weakened"
    severity = Severity.MEDIUM
    description = "Flags test hunks that remove assertions without adding replacements."
    assertion = re.compile(r"\b(?:assert|expect\s*\(|assertEqual|assertTrue|assertFalse)\b")

    def check(self, context: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for item in context.files:
            if item.change.kind != "test" or item.change.status == "deleted":
                continue
            removed = [line for line in item.change.removed_lines if self.assertion.search(line)]
            added = [line for line in item.change.added_lines if self.assertion.search(line)]
            if removed and len(added) < len(removed):
                findings.append(
                    self.finding(
                        "Assertions were removed without equivalent replacements in the same diff.",
                        f"removed {len(removed)} assertion line(s), added {len(added)}",
                        "Check that expectations were not loosened merely to make tests pass.",
                        path=item.change.path,
                    )
                )
        return findings

class DependencyAddedRule(Rule):
    id = "dependencies.added"
    title = "Dependency introduced"
    severity = Severity.MEDIUM
    description = (
        "Reports newly introduced npm or Python dependencies without judging package safety."
    )

    def check(self, context: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for item in context.files:
            change = item.change
            if change.kind != "dependency" or change.status == "deleted":
                continue
            before = _dependencies(change.path, change.before_text)
            after = _dependencies(change.path, change.after_text)
            introduced = sorted(after - before)
            if introduced:
                findings.append(
                    self.finding(
                        "A package dependency was newly introduced; its registry and "
                        "trust status are unverified.",
                        ", ".join(introduced),
                        "Confirm the package name, necessity, provenance, and version policy.",
                        path=change.path,
                    )
                )
        return findings

class ManifestChangedRule(Rule):
    id = "dependencies.manifest_changed"
    title = "Package metadata changed"
    severity = Severity.INFO
    description = (
        "Reports changed dependency manifests or lockfiles when no new dependency was found."
    )

    def check(self, context: RuleContext) -> list[Finding]:
        result: list[Finding] = []
        for item in context.files:
            change = item.change
            introduced = _dependencies(change.path, change.after_text) - _dependencies(
                change.path, change.before_text
            )
            if change.kind in {"dependency", "lockfile"} and not introduced:
                result.append(
                    self.finding(
                        "Dependency metadata is part of this change set.",
                        change.path,
                        "Review version and transitive dependency changes.",
                        path=change.path,
                    )
                )
        return result

class MigrationRule(Rule):
    id = "database.migration_changed"
    title = "Database migration changed"
    severity = Severity.MEDIUM
    description = "Flags created or modified migration files."

    def check(self, context: RuleContext) -> list[Finding]:
        return [
            self.finding(
                "A database migration was created or modified.",
                item.change.path,
                "Review reversibility, locking, and rollout ordering.",
                path=item.change.path,
            )
            for item in context.files
            if item.change.kind == "migration"
        ]

class SensitivePathRule(Rule):
    id = "sensitive.path_changed"
    title = "Sensitive configuration or security path changed"
    severity = Severity.MEDIUM
    description = "Flags auth, security, environment, secrets, or configured sensitive paths."

    def check(self, context: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for item in context.files:
            path = item.change.path
            configured = any(re.search(pattern, path) for pattern in context.config.sensitive_paths)
            if item.change.kind in {"security", "environment"} or configured:
                findings.append(
                    self.finding(
                        "A security- or environment-sensitive path was changed.",
                        path,
                        "Inspect this diff for access-control, secret-handling, and "
                        "deployment impact.",
                        path=path,
                    )
                )
        return findings

class SecretAddedRule(Rule):
    id = "security.possible_secret"
    title = "Possible secret material added"
    severity = Severity.HIGH
    description = "Detects high-confidence secret formats only on added lines."
    patterns = [
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
        re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    ]

    def check(self, context: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for item in context.files:
            for line in item.change.added_lines:
                if any(pattern.search(line) for pattern in self.patterns):
                    findings.append(
                        self.finding(
                            "An added line resembles a private key or access token.",
                            "secret-like value (redacted)",
                            "Remove it from the change, rotate it if real, and use a secret store.",
                            path=item.change.path,
                        )
                    )
                    break
        return findings

class EmptyExceptionRule(Rule):
    id = "errors.silent_exception"
    title = "Silent exception handling added"
    severity = Severity.MEDIUM
    description = "Detects newly added empty exception handlers."
    pattern = re.compile(
        r"(?:except[^\n]*:\n(?:[ +].*\n)*?\+?\s*pass\b|catch\s*\([^)]*\)\s*\{\s*\})", re.I
    )

    def check(self, context: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for item in context.files:
            for hunk in item.change.hunks:
                added_context = "\n".join(line for line in hunk.lines if not line.startswith("-"))
                if self.pattern.search(added_context) and any(
                    "pass" in line or "{}" in line for line in hunk.added_lines
                ):
                    findings.append(
                        self.finding(
                            "A new exception path appears to discard errors without "
                            "handling or logging them.",
                            hunk.header,
                            "Handle the expected exception narrowly or document why "
                            "silence is safe.",
                            path=item.change.path,
                            line=hunk.new_start,
                        )
                    )
                    break
        return findings

class DangerousCommandRule(Rule):
    id = "session.dangerous_command"
    title = "Dangerous shell command observed"
    severity = Severity.HIGH
    description = "Flags destructive command patterns recorded in the agent session."
    pattern = re.compile(
        r"\brm\b(?=[^\n|&]*\s-+[A-Za-z]*[rR])(?=[^\n|&]*\s-+[A-Za-z]*f)"
        r"|\bgit\s+reset\s+--hard\b"
        r"|\bgit\s+clean\s+-+[A-Za-z]*f"
        r"|\bcurl\b[^\n|]*\|\s*(?:sh|bash)\b"
        r"|\bsudo\s+rm\b",
        re.I,
    )

    def check(self, context: RuleContext) -> list[Finding]:
        findings: list[Finding] = []
        for action in context.session.tool_actions:
            for command in shell_commands(action):
                match = self.pattern.search(command)
                if match is not None:
                    findings.append(
                        self.finding(
                            "The transcript records a potentially destructive shell command.",
                            _command_excerpt(command, match.start(), match.end()),
                            "Confirm its target and inspect affected state before committing.",
                        )
                    )
        return findings

class OutsideScopeRule(Rule):
    id = "scope.substantial_outside"
    title = "Substantial change outside apparent scope"
    severity = Severity.MEDIUM
    description = "Flags large diffs classified outside the stated task scope."

    def check(self, context: RuleContext) -> list[Finding]:
        return [
            self.finding(
                "A file outside the apparent request has a substantial diff.",
                f"{item.change.additions + item.change.deletions} changed line(s); "
                f"{'; '.join(item.reasons)}",
                "Review this file first and confirm it belongs in the same commit.",
                path=item.change.path,
            )
            for item in context.files
            if item.scope == ScopeStatus.OUT_OF_SCOPE
            and item.change.additions + item.change.deletions >= 25
        ]

class TodoRule(Rule):
    id = "code.todo_added"
    title = "TODO or FIXME added"
    severity = Severity.LOW
    description = "Detects newly introduced TODO and FIXME markers."
    pattern = re.compile(r"(?:#|//|/\*|<!--)\s*(?:TODO|FIXME)\b")

    def check(self, context: RuleContext) -> list[Finding]:
        return _added_line_findings(
            self,
            context,
            self.pattern,
            "A new TODO or FIXME marker was added.",
            "Decide whether it should be resolved or tracked before commit.",
        )

class DebugStatementRule(Rule):
    id = "code.debug_statement"
    title = "Debug statement added"
    severity = Severity.LOW
    description = "Detects common print, debugger, and console debug statements on added lines."
    pattern = re.compile(
        r"(?:\bconsole\.(?:log|debug)\s*\(|\bdebugger\s*;|\bbreakpoint\s*\(|\bpdb\.set_trace\s*\(|^\s*print\s*\()"
    )

    def check(self, context: RuleContext) -> list[Finding]:
        return _added_line_findings(
            self,
            context,
            self.pattern,
            "A likely debugging statement was added.",
            "Remove it or replace it with intentional structured logging.",
        )

class TemporaryFileRule(Rule):
    id = "files.temporary"
    title = "Generated or temporary file present"
    severity = Severity.LOW
    description = "Flags common editor, cache, backup, and generated output paths."
    pattern = re.compile(
        r"(?:^|/)(?:\.DS_Store|__pycache__|\.pytest_cache|coverage|dist|tmp)(?:/|$)|(?:\.swp|\.tmp|\.bak|~)$",
        re.I,
    )

    def check(self, context: RuleContext) -> list[Finding]:
        return [
            self.finding(
                "A generated-looking or temporary path is included in the changes.",
                item.change.path,
                "Exclude it unless it is an intentional artifact.",
                path=item.change.path,
            )
            for item in context.files
            if self.pattern.search(item.change.path)
        ]

class UnexpectedDocsRule(Rule):
    id = "scope.documentation_changed"
    title = "Documentation changed for a code-only request"
    severity = Severity.INFO
    description = "Reports documentation changes when the request appears explicitly code-only."

    def check(self, context: RuleContext) -> list[Finding]:
        text = context.intent.text.lower()
        code_only = (
            "code only" in text
            or "only change" in text
            or "don't update docs" in text
            or "do not update docs" in text
        )
        if not code_only:
            return []
        return [
            self.finding(
                "Documentation changed despite a code-only constraint.",
                item.change.path,
                "Confirm this documentation edit was requested.",
                path=item.change.path,
            )
            for item in context.files
            if item.change.kind == "documentation"
        ]

RULES: list[Rule] = [
    DeletedTestRule(),
    DisabledTestRule(),
    WeakenedAssertionRule(),
    DependencyAddedRule(),
    ManifestChangedRule(),
    MigrationRule(),
    SensitivePathRule(),
    SecretAddedRule(),
    EmptyExceptionRule(),
    DangerousCommandRule(),
    OutsideScopeRule(),
    TodoRule(),
    DebugStatementRule(),
    TemporaryFileRule(),
    UnexpectedDocsRule(),
]

def available_rules() -> list[tuple[str, Severity, str, str]]:
    return [(rule.id, rule.severity, rule.title, rule.description) for rule in RULES]

def run_rules(context: RuleContext) -> list[Finding]:
    findings: list[Finding] = []
    for rule in RULES:
        if rule.id in context.config.ignored_rules:
            continue
        for finding in rule.check(context):
            if finding.path and (
                context.config.path_ignored(finding.path)
                or context.config.path_trusted(finding.path)
            ):
                continue
            finding.severity = context.config.severity_overrides.get(rule.id, finding.severity)
            findings.append(finding)
    rank = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2, Severity.INFO: 3}
    return sorted(findings, key=lambda item: (rank[item.severity], item.path or "", item.rule_id))

def _added_line_findings(
    rule: Rule, context: RuleContext, pattern: re.Pattern[str], explanation: str, remediation: str
) -> list[Finding]:
    findings: list[Finding] = []
    for item in context.files:
        for hunk in item.change.hunks:
            match = next(
                (line for line in hunk.added_lines if _actionable_match(pattern, line)), None
            )
            if match is not None:
                findings.append(
                    rule.finding(
                        explanation,
                        _truncate(match.strip(), 180),
                        remediation,
                        path=item.change.path,
                        line=hunk.new_start,
                    )
                )
                break
    return findings

def _actionable_match(pattern: re.Pattern[str], line: str) -> bool:
    match = pattern.search(line)
    if match is None:
        return False
    prefix = line[: match.start()]
    return prefix.count('"') % 2 == 0 and prefix.count("'") % 2 == 0

def _dependencies(path: str, text: str | None) -> set[str]:
    if not text:
        return set()
    name = PurePosixPath(path.lower()).name
    try:
        if name == "package.json":
            data = json.loads(text)
            result: set[str] = set()
            for section in (
                "dependencies",
                "devDependencies",
                "peerDependencies",
                "optionalDependencies",
            ):
                values = data.get(section, {}) if isinstance(data, dict) else {}
                if isinstance(values, dict):
                    result.update(str(key) for key in values)
            return result
        if name == "pyproject.toml":
            data = tomllib.loads(text)
            project = data.get("project", {})
            values = project.get("dependencies", []) if isinstance(project, dict) else []
            result = {_python_package(str(value)) for value in values if isinstance(value, str)}
            optional = project.get("optional-dependencies", {}) if isinstance(project, dict) else {}
            if isinstance(optional, dict):
                for group in optional.values():
                    if isinstance(group, list):
                        result.update(_python_package(str(value)) for value in group)
            poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            if isinstance(poetry, dict):
                result.update(str(key) for key in poetry if str(key).lower() != "python")
            return {item for item in result if item}
        if name.startswith("requirements") and name.endswith(".txt"):
            return {
                _python_package(line)
                for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith(("#", "-"))
            }
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, AttributeError, TypeError):
        return set()
    return set()

def _python_package(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    return match.group(1) if match else ""

def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"

def _command_excerpt(command: str, start: int, end: int, width: int = 150) -> str:
    """Show the offending line, windowed around the match, so the evidence explains
    the flag even when the dangerous fragment is buried in a long or multi-line
    command."""
    line_start = command.rfind("\n", 0, start) + 1
    line_end = command.find("\n", end)
    line = command[line_start : line_end if line_end != -1 else len(command)]
    match_in_line = start - line_start
    if len(line) <= width:
        return line.strip()
    lead = max(0, match_in_line - 30)
    fragment = line[lead : lead + width].strip()
    prefix = "…" if lead > 0 else ""
    suffix = "…" if lead + width < len(line) else ""
    return f"{prefix}{fragment}{suffix}"
