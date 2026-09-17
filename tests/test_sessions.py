from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_jsonl

from overscope.models import AgentKind, ToolAction
from overscope.sessions.base import action_kind, shell_commands
from overscope.sessions.claude import ClaudeAdapter
from overscope.sessions.codex import CodexAdapter
from overscope.sessions.discovery import NoSessionError, resolve_session


def test_claude_session_detection_and_parsing(tmp_path: Path) -> None:
    repo = tmp_path / "work" / "app"
    repo.mkdir(parents=True)
    root = tmp_path / "claude"
    transcript = write_jsonl(
        root / "-work-app" / "abc.jsonl",
        [
            {
                "type": "user",
                "sessionId": "abc",
                "cwd": str(repo),
                "timestamp": "2026-01-01T00:00:00Z",
                "message": {"role": "user", "content": "Fix src/users.py"},
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "I will fix it."},
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "Edit",
                            "input": {"file_path": "src/users.py"},
                        },
                    ],
                },
            },
        ],
    )
    adapter = ClaudeAdapter(root)
    candidates = adapter.candidates(repo)
    assert candidates[0].score >= 80
    session = adapter.parse(transcript)
    assert session.id == "abc"
    assert session.cwd == repo
    assert session.user_messages == ["Fix src/users.py"]
    assert session.tool_actions[0].kind == "file_write"

def test_codex_session_detection_and_parsing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    root = tmp_path / "codex"
    transcript = write_jsonl(
        root / "2026" / "rollout-id.jsonl",
        [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "type": "session_meta",
                "payload": {"id": "codex-1", "cwd": str(repo)},
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Add src/api.py"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "c1",
                    "arguments": '{"cmd":"pytest"}',
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "c1",
                    "output": "Exit code: 0",
                },
            },
        ],
    )
    adapter = CodexAdapter(root)
    assert adapter.candidates(repo)[0].score >= 80
    session = adapter.parse(transcript)
    assert session.agent == AgentKind.CODEX
    assert session.cwd == repo
    assert session.user_messages == ["Add src/api.py"]
    assert session.tool_actions[0].success is True

def test_malformed_and_unknown_records_do_not_crash(tmp_path: Path) -> None:
    path = write_jsonl(
        tmp_path / "bad.jsonl",
        [
            "{not json",
            {"type": "future_event", "value": 1},
            {"type": "user", "message": {"role": "user", "content": "Fix it"}},
        ],
    )
    session = ClaudeAdapter(tmp_path).parse(path)
    assert session.malformed_records == 1
    assert session.unknown_records == 1
    assert session.user_messages == ["Fix it"]

def test_repository_session_matching_selects_related(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    claude_root = tmp_path / "claude"
    codex_root = tmp_path / "codex"
    write_jsonl(
        claude_root / "other" / "old.jsonl",
        [{"type": "user", "cwd": "/unrelated", "message": {"role": "user", "content": "Other"}}],
    )
    expected = write_jsonl(
        codex_root / "new.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "right", "cwd": str(repo)}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Fix the app"}],
                },
            },
        ],
    )
    session = resolve_session(repo, adapters=[ClaudeAdapter(claude_root), CodexAdapter(codex_root)])
    assert session.id == "right"
    assert session.path == expected

def test_no_matching_session_is_clear(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(NoSessionError, match="No session confidently matched"):
        resolve_session(
            repo,
            adapters=[ClaudeAdapter(tmp_path / "missing"), CodexAdapter(tmp_path / "also-missing")],
        )

def test_desktop_exec_tool_is_classified_as_shell() -> None:
    assert action_kind("exec") == "shell"
    action = ToolAction(
        "shell",
        "exec",
        {"raw": 'const r = await tools.exec_command({cmd:"uv run pytest"});'},
    )
    assert shell_commands(action) == ["uv run pytest"]
    patch = ToolAction(
        "shell",
        "exec",
        {"raw": 'const patch = "example with escaped {\\"cmd\\": \\"git reset --hard\\"}";'},
    )
    assert shell_commands(patch) == []

def test_codex_commentary_is_not_treated_as_final_response(tmp_path: Path) -> None:
    path = write_jsonl(
        tmp_path / "commentary.jsonl",
        [
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "phase": "commentary",
                    "content": [{"type": "output_text", "text": "Tests pass so far."}],
                },
            }
        ],
    )
    session = CodexAdapter(tmp_path).parse(path)
    assert session.assistant_messages == ["Tests pass so far."]
    assert session.final_response is None

def test_explicit_codex_path_selects_the_correct_adapter(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    claude_root = tmp_path / "claude"
    codex_root = tmp_path / "codex"
    path = write_jsonl(
        codex_root / "rollout.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "codex-explicit", "cwd": str(repo)}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Fix it"}],
                },
            },
        ],
    )
    session = resolve_session(
        repo,
        explicit=str(path),
        adapters=[ClaudeAdapter(claude_root), CodexAdapter(codex_root)],
    )
    assert session.agent == AgentKind.CODEX
    assert session.id == "codex-explicit"

def test_explicit_path_outside_adapter_roots_uses_the_parser_with_signal(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    transcript = write_jsonl(
        tmp_path / "shared-session.jsonl",
        [
            {
                "type": "user",
                "sessionId": "claude-shared",
                "cwd": str(repo),
                "message": {"role": "user", "content": "Fix src/app.py"},
            }
        ],
    )
    session = resolve_session(
        repo,
        explicit=str(transcript),
        adapters=[
            ClaudeAdapter(tmp_path / "claude-root"),
            CodexAdapter(tmp_path / "codex-root"),
        ],
    )
    assert session.agent == AgentKind.CLAUDE
    assert session.id == "claude-shared"

def test_explicit_broken_session_reports_unsupported_schema(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    root = tmp_path / "claude"
    path = write_jsonl(root / "broken.jsonl", ["not json"])
    with pytest.raises(NoSessionError, match="schema may be unsupported"):
        resolve_session(repo, explicit=str(path), adapters=[ClaudeAdapter(root)])
