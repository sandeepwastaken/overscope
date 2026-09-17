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
)
from overscope.rules import RuleContext, run_rules


def context(
    tmp_path: Path, changes: list[FileChange], session: Session | None = None
) -> RuleContext:
    active_session = session or Session("id", AgentKind.CLAUDE, tmp_path / "x")
    intent = Intent("Fix users", "fix", [], ["users"], [], 0.7)
    return RuleContext(
        [ScopedFile(change, ScopeStatus.UNKNOWN, ["unknown"]) for change in changes],
        intent,
        active_session,
        Config(),
    )

def ids(ctx: RuleContext) -> set[str]:
    return {finding.rule_id for finding in run_rules(ctx)}

def test_deleted_test_rule(tmp_path: Path) -> None:
    change = FileChange("tests/test_users.py", "deleted", kind="test", deletions=30)
    assert "tests.deleted" in ids(context(tmp_path, [change]))

def test_new_dependency_rule(tmp_path: Path) -> None:
    before = '{"dependencies":{"fastify":"1.0.0"}}'
    after = '{"dependencies":{"fastify":"1.0.0","left-pad":"1.3.0"}}'
    change = FileChange(
        "package.json", "modified", kind="dependency", before_text=before, after_text=after
    )
    findings = run_rules(context(tmp_path, [change]))
    dependency = next(item for item in findings if item.rule_id == "dependencies.added")
    assert dependency.evidence == "left-pad"
    assert "unverified" in dependency.explanation

def test_debug_statement_only_checks_added_lines(tmp_path: Path) -> None:
    hunk = DiffHunk("@@ -1 +1,2 @@", 1, 1, [" print('old')", "+print('new')"])
    change = FileChange("src/app.py", "modified", hunks=[hunk])
    assert "code.debug_statement" in ids(context(tmp_path, [change]))
    unchanged = FileChange(
        "src/other.py", "modified", hunks=[DiffHunk("@@", 1, 1, [" print('old')"])]
    )
    assert "code.debug_statement" not in ids(context(tmp_path, [unchanged]))

def test_env_and_auth_sensitive_changes(tmp_path: Path) -> None:
    changes = [
        FileChange(".env.production", "modified", kind="environment"),
        FileChange("src/auth/token.py", "modified", kind="security"),
    ]
    findings = [
        item
        for item in run_rules(context(tmp_path, changes))
        if item.rule_id == "sensitive.path_changed"
    ]
    assert {item.path for item in findings} == {".env.production", "src/auth/token.py"}

def test_disabled_test_assertion_and_todo_rules(tmp_path: Path) -> None:
    hunk = DiffHunk(
        "@@ -1 +1 @@", 1, 1, ["-assert result == 2", "+@pytest.mark.skip", "+# TODO fix"]
    )
    change = FileChange("tests/test_math.py", "modified", kind="test", hunks=[hunk])
    result = ids(context(tmp_path, [change]))
    assert {"tests.disabled", "tests.assertion_weakened", "code.todo_added"} <= result

def test_secret_and_silent_exception_rules(tmp_path: Path) -> None:
    fake_token = "+token = 'ghp_" + "a" * 36 + "'"
    hunk = DiffHunk(
        "@@ -1 +1 @@",
        1,
        1,
        ["+except ValueError:", "+    pass", fake_token],
    )
    change = FileChange("src/app.py", "modified", hunks=[hunk])
    result = ids(context(tmp_path, [change]))
    assert "errors.silent_exception" in result
    assert "security.possible_secret" in result
