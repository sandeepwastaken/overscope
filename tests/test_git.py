from __future__ import annotations

import subprocess
from pathlib import Path

from conftest import init_repo

from overscope.git import collect_git_state


def test_collects_staged_unstaged_untracked_and_hunks(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("fixture\nchanged\n", encoding="utf-8")
    (repo / "new.py").write_text("print('debug')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    state = collect_git_state(repo)
    paths = {change.path: change for change in state.changes}
    assert paths["README.md"].staged
    assert paths["README.md"].additions == 1
    assert paths["new.py"].untracked
    assert paths["new.py"].added_lines == ["print('debug')"]

def test_no_git_changes(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    assert collect_git_state(repo).changes == []

def test_deleted_and_renamed_files(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "old.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "old.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "add source"], check=True)
    subprocess.run(["git", "-C", str(repo), "mv", "old.py", "new.py"], check=True)
    state = collect_git_state(repo)
    assert state.changes[0].status == "renamed"
    assert state.changes[0].old_path == "old.py"

def test_initial_repository_staged_file_uses_final_contents_once(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo", commit=False)
    (repo / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "app.py"], check=True)
    state = collect_git_state(repo)
    assert state.head is None
    assert state.changes[0].additions == 2
    assert state.changes[0].added_lines == ["one", "two"]

def test_untracked_binary_file_is_not_decoded(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "asset.bin").write_bytes(b"start\x00end")
    change = collect_git_state(repo).changes[0]
    assert change.binary is True
    assert change.after_text is None
    assert change.hunks == []
