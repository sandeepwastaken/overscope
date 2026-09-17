from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from overscope.config import Config
from overscope.intent import extract_intent
from overscope.models import (
    Attribution,
    Finding,
    GitState,
    OverscopeReport,
    ScopedFile,
    ScopeStatus,
    Session,
    Severity,
)
from overscope.reconcile import reconcile_claims
from overscope.rules import RuleContext, run_rules
from overscope.scope import classify_attribution, classify_scope


def build_report(git: GitState, session: Session, config: Config) -> OverscopeReport:
    intent = extract_intent(session)
    files = classify_scope(git.changes, intent, session)
    _apply_attribution(files, session)
    findings = run_rules(RuleContext(files, intent, session, config))
    reconciliations = reconcile_claims(session, files)
    review_first = _review_first(files, findings)
    warnings = [*config.warnings, *session.warnings]
    if session.malformed_records:
        warnings.append(f"Session parser ignored {session.malformed_records} malformed record(s).")
    return OverscopeReport(
        schema_version="1.0",
        generated_at=datetime.now(UTC).isoformat(),
        repository=str(git.root),
        branch=git.branch,
        head=git.head,
        agent=session.agent.value,
        session_id=session.id,
        session_path=str(session.path),
        intent=intent,
        files=files,
        findings=findings,
        reconciliations=reconciliations,
        review_first=review_first,
        summary=_summary(files, findings),
        warnings=warnings,
    )

def _apply_attribution(files: list[ScopedFile], session: Session) -> None:
    attribution = classify_attribution([item.change for item in files], session)
    for item in files:
        status, reason = attribution.get(item.change.path, (Attribution.UNKNOWN, None))
        item.attribution = status
        item.attribution_reason = reason
        if status == Attribution.UNATTRIBUTED and reason:
            item.reasons = [reason, *item.reasons]

def _review_first(files: list[ScopedFile], findings: list[Finding]) -> list[str]:
    points: defaultdict[str, int] = defaultdict(int)
    severity_points = {Severity.HIGH: 100, Severity.MEDIUM: 45, Severity.LOW: 15, Severity.INFO: 5}
    for finding in findings:
        if finding.path:
            points[finding.path] += severity_points[finding.severity]
    for item in files:
        if item.scope == ScopeStatus.OUT_OF_SCOPE:
            points[item.change.path] += 55
            if item.attribution == Attribution.AGENT:
                points[item.change.path] += 25
        elif item.scope == ScopeStatus.UNKNOWN:
            points[item.change.path] += 20
        if item.change.kind in {"security", "environment", "migration"}:
            points[item.change.path] += 35
        points[item.change.path] += min(20, (item.change.additions + item.change.deletions) // 10)
    return [path for path, _ in sorted(points.items(), key=lambda pair: (-pair[1], pair[0]))[:5]]

def _summary(files: list[ScopedFile], findings: list[Finding]) -> str:
    if not files:
        return "No staged, unstaged, or untracked changes are present."
    high = sum(1 for finding in findings if finding.severity == Severity.HIGH)
    medium = sum(1 for finding in findings if finding.severity == Severity.MEDIUM)
    outside = sum(1 for item in files if item.scope == ScopeStatus.OUT_OF_SCOPE)
    if high:
        return (
            f"{len(files)} changed file(s); {high} high-severity flag(s) "
            "require review before commit."
        )
    if medium or outside:
        return (
            f"{len(files)} changed file(s); review {medium} medium-severity flag(s) "
            f"and {outside} out-of-scope path(s)."
        )
    return f"{len(files)} changed file(s); no high-severity deterministic flags found."
