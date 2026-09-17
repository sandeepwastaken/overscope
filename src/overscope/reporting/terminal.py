from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from overscope.models import (
    Attribution,
    Finding,
    OverscopeReport,
    ScopedFile,
    ScopeStatus,
    Severity,
)
from overscope.reporting.theme import (
    ACCENT,
    DANGER,
    MUTED,
    NEUTRAL,
    SCOPE_BAR_ORDER,
    SCOPE_LABEL,
    SCOPE_STYLE,
    SCOPE_TABLE_ORDER,
    SEVERITY_ORDER,
    SEVERITY_STYLE,
    STATUS_STYLE,
    SUCCESS,
    WARNING,
    Glyphs,
    badge,
    content_width,
    meter,
    resolve_glyphs,
    section_header,
)

_INDENT = (0, 0, 0, 2)

def render_terminal(report: OverscopeReport, console: Console | None = None) -> None:
    output = console or Console()
    glyphs = resolve_glyphs(output)
    width = content_width(output)

    output.print(_banner(report, glyphs, width))
    _emit(output, "INTENT", _intent_body(report, glyphs), glyphs, width, _confidence_note(report))
    _emit(output, "SCOPE", _scope_body(report, glyphs, width), glyphs, width, _scope_note(report))
    _emit(output, "FLAGS", _flags_body(report, glyphs), glyphs, width, _flags_note(report, glyphs))
    _emit(output, "AGENT SAID vs DID", _reconcile_body(report, glyphs), glyphs, width)
    _emit(output, "REVIEW FIRST", _review_body(report, glyphs), glyphs, width)
    if report.warnings:
        _emit(output, "NOTES", _notes_body(report, glyphs), glyphs, width)
    _emit(output, "SUMMARY", _summary_body(report, glyphs), glyphs, width)
    output.print()

def _emit(
    console: Console,
    label: str,
    body: RenderableType,
    glyphs: Glyphs,
    width: int,
    note: Text | None = None,
) -> None:
    console.print()
    console.print(section_header(label, glyphs, width, note))
    console.print(Padding(body, _INDENT))

def _banner(report: OverscopeReport, glyphs: Glyphs, width: int) -> Group:
    label, style, _ = _verdict(report, glyphs)
    title = Text()
    title.append("OVERSCOPE", style=f"bold {ACCENT}")
    pill = badge(label, style, glyphs)
    pad = max(1, width - 6 - len(pill.plain))
    title.append(" " * pad)
    title.append_text(pill)

    meta = Text(no_wrap=True, overflow="ellipsis")
    sep = f"  {glyphs.bullet}  "
    meta.append(report.agent, style=f"bold {ACCENT}")
    meta.append(f"{sep}session {_session_age(report.session_path)}", style=MUTED)
    meta.append(f"{sep}{Path(report.repository).name}", style=MUTED)
    if report.branch:
        meta.append(f"{sep}{report.branch}", style=MUTED)

    additions = sum(item.change.additions for item in report.files)
    deletions = sum(item.change.deletions for item in report.files)
    metrics = Text()
    metrics.append(f"{len(report.files)} files", style="bold")
    metrics.append("    ")
    metrics.append(f"+{additions}", style=SUCCESS if additions else MUTED)
    metrics.append("  ")
    metrics.append(f"{glyphs.minus}{deletions}", style=DANGER if deletions else MUTED)

    rule = Text(glyphs.heavy * width, style=f"{MUTED} {ACCENT}")
    return Group(title, meta, metrics, rule)

def _confidence_note(report: OverscopeReport) -> Text:
    confidence = report.intent.confidence
    style = SUCCESS if confidence >= 0.7 else WARNING if confidence >= 0.4 else DANGER
    note = Text()
    note.append("confidence ", style=MUTED)
    note.append(f"{confidence:.0%}", style=style)
    return note

def _intent_body(report: OverscopeReport, glyphs: Glyphs) -> Group:
    intent = report.intent
    text = intent.text
    quote = Text()
    if len(text) > 1000:
        quote.append(text[:1000].rstrip() + "…")
    else:
        quote.append(text)

    facts = Text()
    facts.append(f"{glyphs.arrow} ", style=ACCENT)
    facts.append("operation ", style=MUTED)
    facts.append(intent.operation or "unspecified", style="" if intent.operation else MUTED)
    facts.append(f"    {glyphs.bullet}    ", style=MUTED)
    facts.append("paths ", style=MUTED)
    if intent.paths:
        facts.append(", ".join(intent.paths[:4]))
    else:
        facts.append("none referenced", style=MUTED)
    if intent.constraints:
        facts.append(f"    {glyphs.bullet}    ", style=MUTED)
        facts.append("constraints ", style=MUTED)
        facts.append(str(len(intent.constraints)))

    renderables: list[RenderableType] = [quote, Text(), facts]
    if len(text) > 1000:
        renderables.append(Text("full instruction retained in --json", style=MUTED))
    return Group(*renderables)

def _scope_note(report: OverscopeReport) -> Text:
    note = Text()
    note.append(f"{len(report.files)}", style="bold")
    note.append(" changed", style=MUTED)
    return note

def _scope_body(report: OverscopeReport, glyphs: Glyphs, width: int) -> RenderableType:
    if not report.files:
        clean = Text()
        clean.append(f"{glyphs.ok} ", style=SUCCESS)
        clean.append("Working tree is clean — nothing to analyze.", style=MUTED)
        return clean

    counts = Counter(item.scope for item in report.files)
    bar_width = max(12, min(28, width - 44))
    segments = [
        (counts[scope], SCOPE_STYLE[scope].replace("bold ", "")) for scope in SCOPE_BAR_ORDER
    ]
    distribution = Text()
    distribution.append_text(meter(segments, bar_width, glyphs))
    distribution.append("   ")
    first = True
    for scope in SCOPE_BAR_ORDER:
        count = counts[scope]
        if not first:
            distribution.append(f"  {glyphs.bullet} ", style=MUTED)
        first = False
        style = SCOPE_STYLE[scope] if count else MUTED
        distribution.append(f"{glyphs.scope[scope]} {count} ", style=style)
        distribution.append(SCOPE_LABEL[scope], style=style if count else MUTED)

    table = Table(box=None, padding=(0, 1), show_header=True, header_style=f"{MUTED}", width=width)
    table.add_column("scope", no_wrap=True)
    table.add_column("file", ratio=5, overflow="fold")
    table.add_column("Δ" if glyphs.unicode else "chg", no_wrap=True, justify="right")
    table.add_column("why", ratio=6, overflow="ellipsis", no_wrap=True, style=MUTED)

    ordered = sorted(
        report.files,
        key=lambda item: (SCOPE_TABLE_ORDER.index(item.scope), item.change.path),
    )
    for item in ordered:
        table.add_row(
            _scope_cell(item.scope, glyphs),
            Text(item.change.path),
            _delta(item, glyphs),
            "; ".join(item.reasons),
        )

    parts: list[RenderableType] = [distribution]
    unattributed = sum(1 for item in report.files if item.attribution == Attribution.UNATTRIBUTED)
    if unattributed:
        note = Text()
        note.append(f"{glyphs.info} ", style=NEUTRAL)
        note.append(
            f"{unattributed} of these were not written by this agent session "
            "(your own edits or another tool)",
            style=MUTED,
        )
        parts.append(note)
    parts.extend([Text(), table])
    return Group(*parts)

def _scope_cell(scope: ScopeStatus, glyphs: Glyphs) -> Text:
    cell = Text()
    cell.append(f"{glyphs.scope[scope]} ", style=SCOPE_STYLE[scope])
    cell.append(SCOPE_LABEL[scope], style=SCOPE_STYLE[scope])
    return cell

def _delta(item: ScopedFile, glyphs: Glyphs) -> Text:
    change = item.change
    if change.binary:
        return Text("binary", style=MUTED)
    delta = Text()
    delta.append(f"+{change.additions}", style=SUCCESS if change.additions else MUTED)
    delta.append(" ")
    delta.append(f"{glyphs.minus}{change.deletions}", style=DANGER if change.deletions else MUTED)
    return delta

def _flags_note(report: OverscopeReport, glyphs: Glyphs) -> Text:
    counts = Counter(finding.severity for finding in report.findings)
    note = Text()
    if not report.findings:
        note.append("clear", style=SUCCESS)
        return note
    present = [severity for severity in SEVERITY_ORDER if counts[severity]]
    for index, severity in enumerate(present):
        if index:
            note.append(f" {glyphs.bullet} ", style=MUTED)
        note.append(f"{counts[severity]} {severity.value.lower()}", style=SEVERITY_STYLE[severity])
    return note

def _flags_body(report: OverscopeReport, glyphs: Glyphs) -> RenderableType:
    if not report.findings:
        body = Text()
        body.append(f"{glyphs.ok} ", style=SUCCESS)
        body.append("No deterministic flags triggered on these changes.", style=MUTED)
        return body

    grid = Table.grid(padding=(0, 1))
    grid.add_column(no_wrap=True, vertical="top")
    grid.add_column(overflow="fold")
    for index, finding in enumerate(report.findings):
        if index:
            grid.add_row("", "")
        grid.add_row(
            Text(glyphs.severity[finding.severity], style=SEVERITY_STYLE[finding.severity]),
            _finding_block(finding, glyphs),
        )
    return grid

def _finding_block(finding: Finding, glyphs: Glyphs) -> Text:
    block = Text()
    block.append(f"{finding.severity.value}  ", style=SEVERITY_STYLE[finding.severity])
    block.append(finding.title, style="bold")
    if finding.path:
        location = finding.path + (f":{finding.line}" if finding.line else "")
        block.append(f"  {location}", style=MUTED)
    block.append("\n")
    block.append(finding.explanation)
    if finding.evidence:
        block.append("\n")
        block.append(finding.evidence, style=MUTED)
    block.append("\n")
    block.append(f"{glyphs.arrow} {finding.remediation}", style=MUTED)
    return block

def _reconcile_body(report: OverscopeReport, glyphs: Glyphs) -> RenderableType:
    if not report.reconciliations:
        return Text("No narrow, verifiable claims were found in the final response.", style=MUTED)
    grid = Table.grid(padding=(0, 1))
    grid.add_column(no_wrap=True, vertical="top")
    grid.add_column(overflow="fold")
    for index, item in enumerate(report.reconciliations):
        if index:
            grid.add_row("", "")
        style = STATUS_STYLE.get(item.status, MUTED)
        block = Text()
        block.append(item.status.replace("_", " ").lower(), style=f"bold {style}")
        block.append(f"  {item.claim}", style="bold")
        block.append("\n")
        block.append(item.explanation)
        if item.evidence:
            block.append("\n")
            block.append(item.evidence, style=MUTED)
        grid.add_row(Text(glyphs.status.get(item.status, glyphs.bullet), style=style), block)
    return grid

def _review_body(report: OverscopeReport, glyphs: Glyphs) -> RenderableType:
    if not report.review_first:
        return Text("Nothing stands out for priority review.", style=MUTED)
    tags = _review_tags(report)
    grid = Table.grid(padding=(0, 1))
    grid.add_column(no_wrap=True, justify="right")
    grid.add_column(overflow="fold")
    for index, path in enumerate(report.review_first, 1):
        line = Text()
        line.append(f"{glyphs.arrow} ", style=ACCENT)
        line.append(path)
        tag = tags.get(path)
        if tag is not None:
            line.append("  ")
            line.append_text(tag)
        grid.add_row(Text(str(index), style=f"bold {ACCENT}"), line)
    return grid

def _review_tags(report: OverscopeReport) -> dict[str, Text]:
    worst: dict[str, Finding] = {}
    for finding in report.findings:
        if not finding.path:
            continue
        current = worst.get(finding.path)
        if current is None or _rank(finding.severity) < _rank(current.severity):
            worst[finding.path] = finding
    scopes = {item.change.path: item.scope for item in report.files}
    tags: dict[str, Text] = {}
    for path in report.review_first:
        best = worst.get(path)
        if best is not None:
            tag = Text()
            tag.append(f"{best.severity.value.lower()}", style=SEVERITY_STYLE[best.severity])
            tag.append(f" · {best.title.lower()}", style=MUTED)
            tags[path] = tag
            continue
        scope = scopes.get(path)
        if scope in {ScopeStatus.OUT_OF_SCOPE, ScopeStatus.UNKNOWN}:
            tags[path] = Text(SCOPE_LABEL[scope], style=SCOPE_STYLE[scope])
    return tags

def _rank(severity: Severity) -> int:
    return SEVERITY_ORDER.index(severity)

def _notes_body(report: OverscopeReport, glyphs: Glyphs) -> RenderableType:
    lines: list[RenderableType] = []
    for warning in report.warnings:
        row = Text()
        row.append(f"{glyphs.warn} ", style=WARNING)
        row.append(warning, style=MUTED)
        lines.append(row)
    return Group(*lines)

def _summary_body(report: OverscopeReport, glyphs: Glyphs) -> Text:
    label, style, glyph = _verdict(report, glyphs)
    body = Text()
    body.append(f"{glyph} ", style=style)
    body.append(label, style=f"bold {style}")
    body.append("   ")
    body.append(report.summary)
    return body

def _verdict(report: OverscopeReport, glyphs: Glyphs) -> tuple[str, str, str]:
    if not report.files:
        return "CLEAN TREE", SUCCESS, glyphs.ok
    counts = Counter(finding.severity for finding in report.findings)
    out_of_scope = sum(1 for item in report.files if item.scope == ScopeStatus.OUT_OF_SCOPE)
    if counts[Severity.HIGH]:
        return "NEEDS REVIEW", DANGER, glyphs.err
    if counts[Severity.MEDIUM] or out_of_scope:
        return "REVIEW SUGGESTED", WARNING, glyphs.warn
    return "LOOKS CLEAN", SUCCESS, glyphs.ok

def _session_age(path: str) -> str:
    try:
        timestamp = Path(path).stat().st_mtime
    except OSError:
        return "time unknown"
    seconds = max(0, int(datetime.now(UTC).timestamp() - timestamp))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86_400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86_400}d ago"
