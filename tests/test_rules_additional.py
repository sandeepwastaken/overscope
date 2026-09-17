from __future__ import annotations

from pathlib import Path

from overscope.config import Config
from overscope.models import (
    AgentKind,
    DiffHunk,
    FileChange,
    Intent,
    ScopedFile,
    ScopeStatus,
    Session,
    Severity,
    ToolAction,
)
from overscope.rules import RuleContext, run_rules


def make_context(
    tmp_path: Path,
    changes: list[FileChange],
    *,
    scope: ScopeStatus = ScopeStatus.UNKNOWN,
    session: Session | None = None,
    intent_text: str = "Fix the users endpoint",
    config: Config | None = None,
) -> RuleContext:
    intent = Intent(intent_text, "fix", [], ["users"], [], 0.7)
    active_session = session or Session("id", AgentKind.CLAUDE, tmp_path / "session.jsonl")
    files = [ScopedFile(change, scope, ["test evidence"]) for change in changes]
    return RuleContext(files, intent, active_session, config or Config())

def findings_for(rule_id: str, context: RuleContext) -> list:
    return [finding for finding in run_rules(context) if finding.rule_id == rule_id]

def test_manifest_and_lockfile_change_rule(tmp_path: Path) -> None:
    manifest = FileChange(
        "package.json",
        "modified",
        kind="dependency",
        before_text='{"dependencies":{"one":"1.0"}}',
        after_text='{"dependencies":{"one":"2.0"}}',
    )
    lockfile = FileChange("uv.lock", "modified", kind="lockfile")
    found = findings_for(
        "dependencies.manifest_changed", make_context(tmp_path, [manifest, lockfile])
    )
    assert {finding.path for finding in found} == {"package.json", "uv.lock"}

def test_python_dependency_is_detected(tmp_path: Path) -> None:
    change = FileChange(
        "pyproject.toml",
        "modified",
        kind="dependency",
        before_text="[project]\ndependencies = []\n",
        after_text='[project]\ndependencies = ["httpx>=1"]\n',
    )
    found = findings_for("dependencies.added", make_context(tmp_path, [change]))
    assert found[0].evidence == "httpx"

def test_migration_rule(tmp_path: Path) -> None:
    change = FileChange("migrations/004_users.sql", "added", kind="migration")
    assert findings_for("database.migration_changed", make_context(tmp_path, [change]))

def test_dangerous_command_rule(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CODEX,
        tmp_path / "session.jsonl",
        tool_actions=[ToolAction("shell", "exec_command", {"cmd": "git reset --hard HEAD~1"})],
    )
    found = findings_for("session.dangerous_command", make_context(tmp_path, [], session=session))
    assert found and "git reset --hard" in found[0].evidence

def test_dangerous_command_rule_ignores_benign_single_file_remove(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CODEX,
        tmp_path / "session.jsonl",
        tool_actions=[
            ToolAction("shell", "exec_command", {"cmd": 'rm -f note.md && echo "removed file"'}),
            ToolAction("shell", "exec_command", {"cmd": "grep -rf pattern src/"}),
        ],
    )
    assert not findings_for(
        "session.dangerous_command", make_context(tmp_path, [], session=session)
    )

def test_dangerous_command_rule_flags_recursive_force_remove(tmp_path: Path) -> None:
    for command in ("rm -rf build", "rm -fr dist", "rm -r -f node_modules"):
        session = Session(
            "id",
            AgentKind.CODEX,
            tmp_path / "session.jsonl",
            tool_actions=[ToolAction("shell", "exec_command", {"cmd": command})],
        )
        found = findings_for(
            "session.dangerous_command", make_context(tmp_path, [], session=session)
        )
        assert found, command

def test_substantial_outside_scope_rule(tmp_path: Path) -> None:
    change = FileChange("src/auth/token.py", "modified", additions=20, deletions=10)
    found = findings_for(
        "scope.substantial_outside",
        make_context(tmp_path, [change], scope=ScopeStatus.OUT_OF_SCOPE),
    )
    assert found and found[0].severity == Severity.MEDIUM

def test_temporary_file_rule(tmp_path: Path) -> None:
    change = FileChange("src/__pycache__/app.pyc", "untracked")
    assert findings_for("files.temporary", make_context(tmp_path, [change]))

def test_explicit_code_only_docs_rule(tmp_path: Path) -> None:
    change = FileChange("README.md", "modified", kind="documentation")
    found = findings_for(
        "scope.documentation_changed",
        make_context(tmp_path, [change], intent_text="Only change code; do not update docs."),
    )
    assert found and found[0].severity == Severity.INFO

def test_rule_config_can_ignore_and_override(tmp_path: Path) -> None:
    hunk = DiffHunk("@@ -0 +1 @@", 0, 1, ["+# TODO: follow up", "+print('debug')"])
    change = FileChange("src/app.py", "modified", hunks=[hunk])
    config = Config(
        ignored_rules={"code.todo_added"},
        severity_overrides={"code.debug_statement": Severity.INFO},
    )
    findings = run_rules(make_context(tmp_path, [change], config=config))
    assert not findings_for("code.todo_added", make_context(tmp_path, [change], config=config))
    debug = next(finding for finding in findings if finding.rule_id == "code.debug_statement")
    assert debug.severity == Severity.INFO
