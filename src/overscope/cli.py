from __future__ import annotations

import enum
import json
from typing import Annotated, Never

import typer
from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from overscope import __version__
from overscope.config import load_config
from overscope.engine import build_report
from overscope.git import GitError, collect_git_state, find_repository
from overscope.models import AgentKind, OverscopeReport, Severity
from overscope.reporting import render_json, render_terminal
from overscope.reporting.theme import (
    ACCENT,
    MUTED,
    SEVERITY_ORDER,
    SEVERITY_STYLE,
    Glyphs,
    content_width,
    resolve_glyphs,
    section_header,
    status_symbol,
)
from overscope.rules import available_rules
from overscope.sessions import AmbiguousSessionError, NoSessionError, resolve_session
from overscope.sessions.discovery import adapters_for


class FailLevel(enum.StrEnum):
    off = "off"
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"

_FAIL_RANK = {
    FailLevel.high: 0,
    FailLevel.medium: 1,
    FailLevel.low: 2,
    FailLevel.info: 3,
}

app = typer.Typer(
    name="overscope",
    help="See what your coding agent actually did before you commit.",
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)
console = Console()
error_console = Console(stderr=True)

def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"overscope {__version__}")
        raise typer.Exit()

@app.callback()
def root(
    ctx: typer.Context,
    session: Annotated[
        str | None, typer.Option("--session", "-s", help="Session ID or transcript path.")
    ] = None,
    agent: Annotated[
        AgentKind | None, typer.Option("--agent", "-a", help="Override agent auto-detection.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit stable machine-readable JSON.")
    ] = False,
    fail_on: Annotated[
        FailLevel,
        typer.Option(
            "--fail-on",
            help="Exit non-zero when a finding at or above this severity exists "
            "(for pre-commit hooks and CI). Default: off.",
        ),
    ] = FailLevel.off,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version", callback=version_callback, is_eager=True, help="Show the version and exit."
        ),
    ] = None,
) -> None:
    """Audit the current working tree against the most relevant coding-agent session."""
    del version
    if ctx.invoked_subcommand is not None:
        return
    try:
        if json_output:
            report = _analyze(session, agent)
        else:
            glyphs = resolve_glyphs(console)
            spinner = "dots" if glyphs.unicode else "line"
            with console.status("Reading session and working tree…", spinner=spinner):
                report = _analyze(session, agent)
    except (GitError, NoSessionError, AmbiguousSessionError) as exc:
        _fail(str(exc), json_output)
    if json_output:
        typer.echo(render_json(report))
    else:
        render_terminal(report, console)
    if _should_fail(report, fail_on):
        raise typer.Exit(1)

def _should_fail(report: OverscopeReport, fail_on: FailLevel) -> bool:
    if fail_on == FailLevel.off:
        return False
    threshold = _FAIL_RANK[fail_on]
    order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2, Severity.INFO: 3}
    return any(order[finding.severity] <= threshold for finding in report.findings)

def _analyze(session: str | None, agent: AgentKind | None) -> OverscopeReport:
    git = collect_git_state()
    config = load_config(git.root)
    selected_agent = agent
    if selected_agent is None and config.preferred_agent:
        try:
            selected_agent = AgentKind(config.preferred_agent.lower())
        except ValueError:
            config.warnings.append(f"Ignored unknown preferred agent: {config.preferred_agent}")
    selected_session = resolve_session(git.root, agent=selected_agent, explicit=session)
    return build_report(git, selected_session, config)

@app.command()
def doctor() -> None:
    """Diagnose repository and coding-agent session discovery."""
    glyphs = resolve_glyphs(console)
    width = content_width(console)
    try:
        repository = find_repository()
    except GitError as exc:
        console.print(_signal("err", glyphs, str(exc)))
        raise typer.Exit(1) from exc

    console.print()
    console.print(section_header("OVERSCOPE DOCTOR", glyphs, width))

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=MUTED, no_wrap=True, justify="right")
    grid.add_column(overflow="fold")
    grid.add_row("repository", _signal("ok", glyphs, str(repository)))

    config_path = repository / ".overscope.toml"
    config = load_config(repository)
    if config_path.exists():
        grid.add_row("config", _signal("ok", glyphs, str(config_path)))
    else:
        grid.add_row("config", Text("none (defaults active)", style=MUTED))
    for warning in config.warnings:
        grid.add_row("", _signal("warn", glyphs, warning))

    any_match = False
    for adapter in adapters_for():
        name = adapter.kind.value
        root_exists = adapter.root.is_dir()
        candidates = adapter.candidates(repository) if root_exists else []
        matching = [item for item in candidates if item.score >= 80]
        any_match = any_match or bool(matching)
        if not root_exists:
            status = _signal("info", glyphs, "transcript location not found")
        elif matching:
            status = _signal("ok", glyphs, f"{len(matching)} matching · {len(candidates)} scanned")
        else:
            status = _signal(
                "warn", glyphs, f"0 matching · {len(candidates)} scanned — pass --session to choose"
            )
        grid.add_row(f"{name} sessions", status)
        grid.add_row("", Text(str(adapter.root), style=MUTED))
        if matching:
            best = Text()
            best.append(matching[0].id, style=ACCENT)
            best.append(f"  {matching[0].reasons[0]}", style=MUTED)
            grid.add_row("", best)

    grid.add_row(
        "privacy",
        _signal("ok", glyphs, "local only — no network, telemetry, uploads, or analytics"),
    )
    console.print(Padding(grid, (1, 0, 0, 2)))

    if any_match:
        verdict = _signal("ok", glyphs, "Ready — run `overscope` to analyze the latest session.")
    else:
        verdict = _signal(
            "warn",
            glyphs,
            "No session matched this repo yet. Run your agent here, or pass --session PATH.",
        )
    console.print(Padding(verdict, (1, 0, 0, 2)))
    console.print()

@app.command("rules")
def rules_command() -> None:
    """List deterministic checks and their default severities."""
    glyphs = resolve_glyphs(console)
    width = content_width(console)
    rules = sorted(available_rules(), key=lambda row: (SEVERITY_ORDER.index(row[1]), row[0]))

    note = Text()
    note.append(f"{len(rules)} checks", style=MUTED)
    console.print()
    console.print(section_header("OVERSCOPE RULES", glyphs, width, note))

    table = Table(box=None, padding=(0, 2), show_header=True, header_style=MUTED, width=width)
    table.add_column("sev", no_wrap=True)
    table.add_column("rule", no_wrap=True, style=ACCENT)
    table.add_column("what it checks", overflow="fold")
    for rule_id, severity, title, description in rules:
        gutter = Text()
        gutter.append(f"{glyphs.severity[severity]} ", style=SEVERITY_STYLE[severity])
        gutter.append(severity.value.lower(), style=SEVERITY_STYLE[severity])
        detail = Text()
        detail.append(title, style="bold")
        detail.append(f"  —  {description}", style=MUTED)
        table.add_row(gutter, rule_id, detail)
    console.print(Padding(table, (1, 0, 0, 2)))
    console.print()

def _signal(kind: str, glyphs: Glyphs, text: str, text_style: str = "") -> Text:
    glyph, style = status_symbol(kind, glyphs)
    signal = Text()
    signal.append(f"{glyph} ", style=style)
    signal.append(text, style=text_style)
    return signal

def _fail(message: str, json_output: bool) -> Never:
    if json_output:
        typer.echo(
            json.dumps(
                {"error": {"message": message, "type": "analysis_error"}, "schema_version": "1.0"},
                indent=2,
            )
        )
    else:
        error_console.print()
        error_console.print(_signal("err", resolve_glyphs(error_console), message))
        error_console.print()
    raise typer.Exit(2)

def main() -> None:
    app()

if __name__ == "__main__":
    main()
