from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from overscope.models import AgentKind, Session


@pytest.fixture
def base_session(tmp_path: Path) -> Session:
    return Session(
        id="session-1",
        agent=AgentKind.CLAUDE,
        path=tmp_path / "session-1.jsonl",
        cwd=tmp_path,
        user_messages=["Add pagination to the users endpoint and update its tests."],
        assistant_messages=["Implemented pagination and added tests."],
    )

def write_jsonl(path: Path, records: list[Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [item if isinstance(item, str) else json.dumps(item) for item in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

def init_repo(path: Path, *, commit: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True
    )
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Overscope Test"], check=True)
    if commit:
        (path / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)
    return path
