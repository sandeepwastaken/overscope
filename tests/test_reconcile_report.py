from __future__ import annotations

import json
from pathlib import Path

from overscope.config import Config
from overscope.engine import build_report
from overscope.models import (
    AgentKind,
    Attribution,
    DiffHunk,
    FileChange,
    GitState,
    ScopedFile,
    ScopeStatus,
    Session,
    ToolAction,
)
from overscope.reconcile import reconcile_claims
from overscope.reporting import render_json


def test_said_vs_did_mismatches_and_test_claim(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CLAUDE,
        tmp_path / "x.jsonl",
        assistant_messages=["Changed 2 files and added tests. All tests pass."],
    )
    files = [ScopedFile(FileChange("src/a.py", "modified"), ScopeStatus.UNKNOWN, [])]
    result = reconcile_claims(session, files)
    statuses = {(item.claim, item.status) for item in result}
    assert ("Changed-file count", "MISMATCH") in statuses
    assert ("Tests were added", "MISMATCH") in statuses
    assert ("Tests pass", "UNVERIFIED") in statuses

def test_undisclosed_changes_flag_files_the_agent_wrote_but_never_named(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CLAUDE,
        tmp_path / "x.jsonl",
        assistant_messages=["I updated src/api/users.py to add pagination."],
    )
    files = [
        ScopedFile(FileChange("src/api/users.py", "modified"), ScopeStatus.IN_SCOPE, [],
                   attribution=Attribution.AGENT),
        ScopedFile(FileChange("src/auth/token.py", "modified"), ScopeStatus.OUT_OF_SCOPE, [],
                   attribution=Attribution.AGENT),
    ]
    result = reconcile_claims(session, files)
    undisclosed = next(item for item in result if item.claim == "Undisclosed changes")
    assert undisclosed.status == "MISMATCH"
    assert "src/auth/token.py" in (undisclosed.evidence or "")

def test_undisclosed_not_reported_when_agent_names_no_files(tmp_path: Path) -> None:
    session = Session(
        "id", AgentKind.CLAUDE, tmp_path / "x.jsonl", assistant_messages=["Done, all set."]
    )
    files = [
        ScopedFile(FileChange("src/api/users.py", "modified"), ScopeStatus.IN_SCOPE, [],
                   attribution=Attribution.AGENT),
    ]
    result = reconcile_claims(session, files)
    assert all(item.claim != "Undisclosed changes" for item in result)

def test_successful_test_claim_requires_captured_success(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CODEX,
        tmp_path / "x.jsonl",
        assistant_messages=["All tests passed."],
        final_message="All tests passed.",
        tool_actions=[ToolAction("shell", "exec_command", {"cmd": "uv run pytest"}, success=True)],
    )
    result = reconcile_claims(session, [])
    assert result[0].status == "SUPPORTED"

def test_json_output_schema_and_no_changes(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    path.write_text("", encoding="utf-8")
    session = Session(
        "id", AgentKind.CLAUDE, path, user_messages=["Fix src/app.py"], assistant_messages=["Done."]
    )
    report = build_report(GitState(tmp_path, "main", "abc", []), session, Config())
    payload = json.loads(render_json(report))
    assert payload["schema_version"] == "1.0"
    assert payload["files"] == []
    assert payload["summary"].startswith("No staged")
    assert "\x1b" not in render_json(report)

def test_json_omits_internal_snapshots_and_bounds_hunk_excerpts(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    path.write_text("", encoding="utf-8")
    session = Session(
        "id",
        AgentKind.CLAUDE,
        path,
        user_messages=["Fix src/app.py"],
        assistant_messages=["Done."],
    )
    change = FileChange(
        "src/app.py",
        "modified",
        additions=100,
        before_text="private old source",
        after_text="private new source",
        hunks=[DiffHunk("@@ -1 +1 @@", 1, 1, [f"+line {index}" for index in range(100)])],
    )
    report = build_report(GitState(tmp_path, "main", "abc", [change]), session, Config())
    payload = json.loads(render_json(report))
    serialized_change = payload["files"][0]["change"]
    assert "before_text" not in serialized_change
    assert "after_text" not in serialized_change
    assert len(serialized_change["hunks"][0]["lines"]) == 80
    assert serialized_change["hunks"][0]["truncated"] is True
