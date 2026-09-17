from __future__ import annotations

import re
import subprocess
from pathlib import Path

from overscope.git.file_kinds import classify_file
from overscope.models import DiffHunk, FileChange, GitState


class GitError(RuntimeError):
    pass

def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitError(f"Could not run git: {exc}") from exc
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise GitError(detail)
    return result

def find_repository(start: Path | None = None) -> Path:
    location = (start or Path.cwd()).resolve()
    result = _git(location, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise GitError(f"Not inside a Git repository: {location}")
    return Path(result.stdout.strip()).resolve()

def collect_git_state(start: Path | None = None) -> GitState:
    root = find_repository(start)
    head_result = _git(root, "rev-parse", "HEAD", check=False)
    head = head_result.stdout.strip() if head_result.returncode == 0 else None
    branch_result = _git(root, "branch", "--show-current", check=False)
    branch = branch_result.stdout.strip() or None
    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    changes = [_load_change(root, entry, head) for entry in _parse_status(status)]
    return GitState(root=root, branch=branch, head=head, changes=changes)

def _parse_status(raw: str) -> list[dict[str, str | bool | None]]:
    chunks = raw.split("\0")
    entries: list[dict[str, str | bool | None]] = []
    index = 0
    while index < len(chunks):
        record = chunks[index]
        index += 1
        if not record or len(record) < 4:
            continue
        xy = record[:2]
        path = record[3:]
        old_path: str | None = None
        if ("R" in xy or "C" in xy) and index < len(chunks):
            old_path = chunks[index]
            index += 1
        entries.append(
            {
                "path": path,
                "old_path": old_path,
                "xy": xy,
                "staged": xy[0] not in {" ", "?"},
                "unstaged": xy[1] not in {" ", "?"},
                "untracked": xy == "??",
            }
        )
    return entries

def _load_change(root: Path, entry: dict[str, str | bool | None], head: str | None) -> FileChange:
    path = str(entry["path"])
    xy = str(entry["xy"])
    untracked = bool(entry["untracked"])
    status = _status_name(xy)
    disk_path = root / path
    after_text, binary = _read_worktree_file(disk_path) if status != "deleted" else (None, False)
    before_text = _read_head_file(root, str(entry.get("old_path") or path), head)

    if untracked or (head is None and after_text is not None):
        lines = [] if after_text is None else after_text.splitlines()
        hunks = (
            [
                DiffHunk(
                    header="@@ -0,0 +1 @@",
                    old_start=0,
                    new_start=1,
                    lines=[f"+{x}" for x in lines],
                )
            ]
            if after_text is not None
            else []
        )
        additions, deletions = len(lines), 0
    else:
        diff = _combined_diff(root, path, head)
        hunks = parse_hunks(diff)
        additions = sum(len(hunk.added_lines) for hunk in hunks)
        deletions = sum(len(hunk.removed_lines) for hunk in hunks)
        binary = binary or "Binary files" in diff or "GIT binary patch" in diff

    return FileChange(
        path=path,
        old_path=str(entry["old_path"]) if entry.get("old_path") else None,
        status=status,
        staged=bool(entry["staged"]),
        unstaged=bool(entry["unstaged"]),
        untracked=untracked,
        additions=additions,
        deletions=deletions,
        binary=binary,
        kind=classify_file(path),
        hunks=hunks,
        before_text=before_text,
        after_text=after_text,
    )

def _status_name(xy: str) -> str:
    if xy == "??":
        return "untracked"
    if "D" in xy:
        return "deleted"
    if "R" in xy:
        return "renamed"
    if "C" in xy:
        return "copied"
    if "A" in xy:
        return "added"
    return "modified"

def _combined_diff(root: Path, path: str, head: str | None) -> str:
    if head:
        return _git(root, "diff", "--no-ext-diff", "--unified=3", "HEAD", "--", path).stdout
    cached = _git(root, "diff", "--cached", "--no-ext-diff", "--unified=3", "--", path).stdout
    unstaged = _git(root, "diff", "--no-ext-diff", "--unified=3", "--", path).stdout
    return cached + unstaged

def _read_head_file(root: Path, path: str, head: str | None) -> str | None:
    if not head:
        return None
    result = _git(root, "show", f"HEAD:{path}", check=False)
    if result.returncode != 0 or "\x00" in result.stdout:
        return None
    return result.stdout

def _read_worktree_file(path: Path) -> tuple[str | None, bool]:
    if not path.is_file():
        return None, False
    try:
        data = path.read_bytes()
    except OSError:
        return None, False
    if b"\x00" in data[:8192]:
        return None, True
    if len(data) > 2_000_000:
        return None, False
    return data.decode("utf-8", errors="replace"), False

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")

def parse_hunks(diff: str) -> list[DiffHunk]:
    hunks: list[DiffHunk] = []
    current: DiffHunk | None = None
    for line in diff.splitlines():
        match = HUNK_RE.match(line)
        if match:
            current = DiffHunk(
                header=line,
                old_start=int(match.group(1)),
                new_start=int(match.group(2)),
                lines=[],
            )
            hunks.append(current)
        elif current is not None and not line.startswith("diff --git"):
            current.lines.append(line)
    return hunks
