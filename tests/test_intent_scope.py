from __future__ import annotations

from pathlib import Path

from overscope.intent import extract_intent
from overscope.models import AgentKind, FileChange, ScopeStatus, Session
from overscope.scope import classify_scope


def test_intent_uses_recent_instruction_not_acknowledgement(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CLAUDE,
        tmp_path / "x.jsonl",
        user_messages=[
            "Set up the repo",
            "Please add pagination in src/users/routes.py only, without changing auth.",
            "thanks",
        ],
    )
    intent = extract_intent(session)
    assert intent.operation == "add"
    assert "src/users/routes.py" in intent.paths
    assert any("without" in constraint for constraint in intent.constraints)
    assert "pagination" in intent.keywords

def test_scope_classifies_in_adjacent_and_out(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CLAUDE,
        tmp_path / "x.jsonl",
        user_messages=["Add pagination to src/users/routes.py and update tests."],
    )
    intent = extract_intent(session)
    changes = [
        FileChange("src/users/routes.py", "modified"),
        FileChange("tests/users/test_routes.py", "modified", kind="test"),
        FileChange("src/auth/token.py", "modified"),
    ]
    scoped = {item.change.path: item for item in classify_scope(changes, intent, session)}
    assert scoped["src/users/routes.py"].scope == ScopeStatus.IN_SCOPE
    assert scoped["tests/users/test_routes.py"].scope in {
        ScopeStatus.IN_SCOPE,
        ScopeStatus.ADJACENT,
    }
    assert scoped["src/auth/token.py"].scope == ScopeStatus.OUT_OF_SCOPE
    assert scoped["src/auth/token.py"].reasons

def test_scope_prefers_unknown_without_clear_signal(tmp_path: Path) -> None:
    session = Session("id", AgentKind.CLAUDE, tmp_path / "x", user_messages=["Please fix it."])
    intent = extract_intent(session)
    result = classify_scope([FileChange("src/mystery.py", "modified")], intent, session)
    assert result[0].scope == ScopeStatus.UNKNOWN

def test_negative_constraint_marks_forbidden_file_out_of_scope(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CLAUDE,
        tmp_path / "x.jsonl",
        user_messages=["Add pagination to src/api/users.py. Don't change auth."],
    )
    intent = extract_intent(session)
    assert "auth" not in intent.keywords
    scoped = {
        item.change.path: item
        for item in classify_scope(
            [
                FileChange("src/api/users.py", "modified"),
                FileChange("src/auth/token.py", "modified"),
            ],
            intent,
            session,
        )
    }
    assert scoped["src/api/users.py"].scope == ScopeStatus.IN_SCOPE
    assert scoped["src/auth/token.py"].scope == ScopeStatus.OUT_OF_SCOPE
    assert any("not to change" in reason for reason in scoped["src/auth/token.py"].reasons)

def test_negative_constraint_stops_at_conjunction(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CLAUDE,
        tmp_path / "x.jsonl",
        user_messages=[
            "Refactor src/billing.py. Don't touch the API layer and keep tests passing."
        ],
    )
    intent = extract_intent(session)
    assert "api" in intent.avoid
    assert "tests" not in intent.avoid
    assert "passing" not in intent.avoid

def test_negative_constraint_recognizes_dotfile(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CLAUDE,
        tmp_path / "x.jsonl",
        user_messages=["Add migrations/004.sql. Don't change .env."],
    )
    intent = extract_intent(session)
    assert "env" in intent.avoid
    assert "env" not in intent.keywords
    scoped = classify_scope([FileChange(".env", "untracked")], intent, session)
    assert scoped[0].scope == ScopeStatus.OUT_OF_SCOPE

def test_unrelated_sibling_in_flat_src_is_not_adjacent(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CLAUDE,
        tmp_path / "x.jsonl",
        user_messages=["Fix the formatting in src/dates.py."],
    )
    intent = extract_intent(session)
    scoped = {
        item.change.path: item
        for item in classify_scope(
            [FileChange("src/dates.py", "modified"), FileChange("src/cache.py", "modified")],
            intent,
            session,
        )
    }
    assert scoped["src/dates.py"].scope == ScopeStatus.IN_SCOPE
    assert scoped["src/cache.py"].scope != ScopeStatus.ADJACENT

def test_vague_intent_does_not_confidently_flag_out_of_scope(tmp_path: Path) -> None:
    session = Session(
        "id",
        AgentKind.CLAUDE,
        tmp_path / "x.jsonl",
        user_messages=["Improve the console/terminal UI and make reports easier to scan."],
    )
    intent = extract_intent(session)
    assert intent.paths == []
    changes = [
        FileChange("src/reporting/terminal.py", "modified"),
        FileChange("src/db/pool.py", "modified"),
    ]
    scoped = classify_scope(changes, intent, session)
    assert all(item.scope != ScopeStatus.OUT_OF_SCOPE for item in scoped)
