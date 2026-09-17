from __future__ import annotations

from pathlib import Path

from overscope.models import AgentKind, Attribution, FileChange, Session, ToolAction
from overscope.scope import classify_attribution


def _session(actions: list[ToolAction]) -> Session:
    return Session("s", AgentKind.CLAUDE, Path("s.jsonl"), tool_actions=actions)

def test_agent_written_file_is_attributed_to_agent() -> None:
    session = _session([ToolAction("file_write", "Edit", {"file_path": "src/api/users.py"})])
    result = classify_attribution([FileChange("src/api/users.py", "modified")], session)
    status, reason = result["src/api/users.py"]
    assert status == Attribution.AGENT
    assert reason

def test_absolute_tool_path_matches_relative_change() -> None:
    session = _session(
        [ToolAction("file_write", "Write", {"file_path": "/home/me/proj/src/a.py"})]
    )
    result = classify_attribution([FileChange("src/a.py", "modified")], session)
    assert result["src/a.py"][0] == Attribution.AGENT

def test_change_the_agent_never_wrote_is_unattributed() -> None:
    session = _session([ToolAction("file_write", "Edit", {"file_path": "src/api/users.py"})])
    changes = [FileChange("src/api/users.py", "modified"), FileChange("src/other.py", "modified")]
    result = classify_attribution(changes, session)
    assert result["src/other.py"][0] == Attribution.UNATTRIBUTED

def test_no_write_signal_yields_unknown_not_a_false_accusation() -> None:
    session = _session([ToolAction("file_read", "Read", {"file_path": "src/api/users.py"})])
    result = classify_attribution([FileChange("src/other.py", "modified")], session)
    assert result["src/other.py"][0] == Attribution.UNKNOWN

def test_deletion_via_shell_rm_is_attributed_to_agent() -> None:
    session = _session(
        [
            ToolAction("file_write", "Edit", {"file_path": "src/api/users.py"}),
            ToolAction("shell", "Bash", {"command": "rm test/users.test.js"}),
        ]
    )
    result = classify_attribution([FileChange("test/users.test.js", "deleted")], session)
    assert result["test/users.test.js"][0] == Attribution.AGENT

def test_apply_patch_targets_are_attributed() -> None:
    patch = "apply_patch <<'EOF'\n*** Update File: src/core/engine.py\n+x = 1\nEOF"
    session = _session([ToolAction("shell", "exec", {"command": patch})])
    result = classify_attribution([FileChange("src/core/engine.py", "modified")], session)
    assert result["src/core/engine.py"][0] == Attribution.AGENT
