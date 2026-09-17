"""A small, cohesive terminal design system shared by every Overscope view.

The goal is one visual language: the same accent, the same status glyphs, the same
section headers everywhere. Meaning is encoded by *shape* first (so the report stays
readable with ``NO_COLOR`` or on a monochrome terminal) and reinforced by colour.
Everything degrades: an ASCII glyph set is used when the terminal cannot render
Unicode, and Rich itself strips styling on non-TTY or ``NO_COLOR`` output.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from rich.cells import cell_len
from rich.console import Console
from rich.text import Text

from overscope.models import ScopeStatus, Severity

ACCENT = "cyan"
SUCCESS = "green"
WARNING = "yellow"
DANGER = "red"
NEUTRAL = "blue"
MUTED = "dim"

MAX_WIDTH = 96

SEVERITY_STYLE: dict[Severity, str] = {
    Severity.HIGH: "bold red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
    Severity.INFO: "dim",
}
SEVERITY_ORDER = [Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]

SCOPE_STYLE: dict[ScopeStatus, str] = {
    ScopeStatus.IN_SCOPE: "green",
    ScopeStatus.ADJACENT: "cyan",
    ScopeStatus.OUT_OF_SCOPE: "bold red",
    ScopeStatus.UNKNOWN: "yellow",
}
SCOPE_LABEL: dict[ScopeStatus, str] = {
    ScopeStatus.IN_SCOPE: "in scope",
    ScopeStatus.ADJACENT: "adjacent",
    ScopeStatus.OUT_OF_SCOPE: "out of scope",
    ScopeStatus.UNKNOWN: "unknown",
}
SCOPE_BAR_ORDER = [
    ScopeStatus.IN_SCOPE,
    ScopeStatus.ADJACENT,
    ScopeStatus.UNKNOWN,
    ScopeStatus.OUT_OF_SCOPE,
]
SCOPE_TABLE_ORDER = [
    ScopeStatus.OUT_OF_SCOPE,
    ScopeStatus.UNKNOWN,
    ScopeStatus.ADJACENT,
    ScopeStatus.IN_SCOPE,
]

STATUS_STYLE: dict[str, str] = {
    "SUPPORTED": "green",
    "UNVERIFIED": "yellow",
    "MISMATCH": "bold red",
    "INSUFFICIENT_EVIDENCE": "dim",
}

@dataclass(frozen=True)
class Glyphs:
    """A glyph set. Two instances exist: rich Unicode and a plain-ASCII fallback."""

    unicode: bool
    bar: str
    rule: str
    heavy: str
    fill: str
    track: str
    arrow: str
    bullet: str
    minus: str
    ok: str
    warn: str
    err: str
    info: str
    severity: dict[Severity, str]
    scope: dict[ScopeStatus, str]
    status: dict[str, str]

_UNICODE = Glyphs(
    unicode=True,
    bar="▌",
    rule="─",
    heavy="━",
    fill="█",
    track="░",
    arrow="→",
    bullet="·",
    minus="−",
    ok="✓",
    warn="⚠",
    err="✗",
    info="ℹ",
    severity={
        Severity.HIGH: "█",
        Severity.MEDIUM: "▓",
        Severity.LOW: "▒",
        Severity.INFO: "░",
    },
    scope={
        ScopeStatus.IN_SCOPE: "✓",
        ScopeStatus.ADJACENT: "≈",
        ScopeStatus.OUT_OF_SCOPE: "!",
        ScopeStatus.UNKNOWN: "?",
    },
    status={
        "SUPPORTED": "✓",
        "UNVERIFIED": "⚠",
        "MISMATCH": "✗",
        "INSUFFICIENT_EVIDENCE": "–",
    },
)
_ASCII = Glyphs(
    unicode=False,
    bar="|",
    rule="-",
    heavy="=",
    fill="#",
    track=".",
    arrow="->",
    bullet="*",
    minus="-",
    ok="OK",
    warn="!",
    err="x",
    info="i",
    severity={
        Severity.HIGH: "#",
        Severity.MEDIUM: "=",
        Severity.LOW: "-",
        Severity.INFO: ".",
    },
    scope={
        ScopeStatus.IN_SCOPE: "+",
        ScopeStatus.ADJACENT: "~",
        ScopeStatus.OUT_OF_SCOPE: "!",
        ScopeStatus.UNKNOWN: "?",
    },
    status={
        "SUPPORTED": "+",
        "UNVERIFIED": "!",
        "MISMATCH": "x",
        "INSUFFICIENT_EVIDENCE": "-",
    },
)

def resolve_glyphs(console: Console) -> Glyphs:
    """Pick the Unicode or ASCII glyph set for a console."""
    if os.environ.get("OVERSCOPE_ASCII"):
        return _ASCII
    encoding = (console.encoding or "").lower()
    return _UNICODE if "utf" in encoding else _ASCII

def content_width(console: Console) -> int:
    return max(40, min(console.width, MAX_WIDTH))

def section_header(label: str, glyphs: Glyphs, width: int, note: Text | None = None) -> Text:
    """``▌ LABEL ───────────────────────────────  note`` — the one heading style."""
    head = Text()
    head.append(f"{glyphs.bar} ", style=ACCENT)
    head.append(label.upper(), style="bold")
    head.append(" ")
    note_width = (cell_len(note.plain) + 1) if note is not None else 0
    fill = max(1, width - cell_len(head.plain) - note_width)
    head.append(glyphs.rule * fill, style=MUTED)
    if note is not None:
        head.append(" ")
        head.append_text(note)
    return head

def badge(text: str, style: str, glyphs: Glyphs) -> Text:
    """A filled status pill, e.g. the report verdict. Uses reverse video for weight."""
    return Text(f" {text} ", style=f"reverse bold {style}")

def status_symbol(kind: str, glyphs: Glyphs) -> tuple[str, str]:
    """Return ``(glyph, style)`` for a generic ok/warn/err/info signal."""
    table = {
        "ok": (glyphs.ok, SUCCESS),
        "warn": (glyphs.warn, WARNING),
        "err": (glyphs.err, DANGER),
        "info": (glyphs.info, ACCENT),
    }
    return table.get(kind, (glyphs.bullet, MUTED))

def meter(segments: list[tuple[int, str]], width: int, glyphs: Glyphs) -> Text:
    """A single proportional bar built from ``(count, style)`` segments.

    Rounding is corrected against the largest segment so the filled cells always sum
    to exactly ``width`` when there is anything to show.
    """
    total = sum(count for count, _ in segments)
    bar = Text()
    if total <= 0:
        bar.append(glyphs.track * width, style=MUTED)
        return bar
    lengths = [round(count / total * width) for count, _ in segments]
    drift = width - sum(lengths)
    if lengths:
        biggest = max(range(len(lengths)), key=lambda index: lengths[index])
        lengths[biggest] = max(0, lengths[biggest] + drift)
    rendered = 0
    for (count, style), length in zip(segments, lengths, strict=True):
        if count > 0 and length > 0:
            bar.append(glyphs.fill * length, style=style)
            rendered += length
    if rendered < width:
        bar.append(glyphs.track * (width - rendered), style=MUTED)
    return bar
