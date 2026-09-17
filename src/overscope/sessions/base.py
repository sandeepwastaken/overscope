from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from overscope.models import AgentKind, Session, SessionCandidate

NESTED_COMMAND_RE = re.compile(r'\bcmd\s*:\s*"((?:\\.|[^"\\])*)"')

class SessionAdapter(ABC):
    kind: AgentKind
    root: Path

    @abstractmethod
    def candidates(self, repository: Path, limit: int = 80) -> list[SessionCandidate]: ...

    @abstractmethod
    def parse(self, path: Path) -> Session: ...

    def find_explicit(self, value: str) -> Path | None:
        supplied = Path(value).expanduser()
        if supplied.is_file():
            return supplied.resolve()
        if not self.root.exists():
            return None
        direct = list(self.root.rglob(f"{value}.jsonl"))
        if direct:
            return max(direct, key=lambda item: item.stat().st_mtime)
        partial = [item for item in self.root.rglob("*.jsonl") if value in item.stem]
        return max(partial, key=lambda item: item.stat().st_mtime) if partial else None

def jsonl_records(path: Path) -> Iterator[tuple[int, dict[str, Any] | None]]:
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                yield number, None
                continue
            yield number, value if isinstance(value, dict) else None

def content_text(content: Any) -> list[str]:
    if isinstance(content, str):
        return [content] if content.strip() else []
    if not isinstance(content, list):
        return []
    texts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type in {"text", "input_text", "output_text"}:
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
    return texts

def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

def parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}
    return parsed if isinstance(parsed, dict) else {"raw": value}

def action_kind(name: str) -> str:
    lowered = name.lower()
    if lowered in {"bash", "shell", "exec", "exec_command", "run_command", "terminal"}:
        return "shell"
    if any(token in lowered for token in ("write", "edit", "patch", "create")):
        return "file_write"
    if any(token in lowered for token in ("read", "view", "open", "search", "glob", "grep")):
        return "file_read"
    return "tool"

def shell_commands(action: Any) -> list[str]:
    """Return executed commands without mistaking surrounding patch payloads for commands."""
    if getattr(action, "kind", None) != "shell":
        return []
    action_input = getattr(action, "input", {})
    if not isinstance(action_input, dict):
        return []
    direct = action_input.get("command") or action_input.get("cmd")
    if isinstance(direct, str):
        return [direct]
    raw = action_input.get("raw")
    if not isinstance(raw, str):
        return []
    if str(getattr(action, "name", "")).lower() != "exec":
        return [raw]
    commands: list[str] = []
    for match in NESTED_COMMAND_RE.finditer(raw):
        try:
            commands.append(json.loads(f'"{match.group(1)}"'))
        except json.JSONDecodeError:
            commands.append(match.group(1))
    return commands

def probe_file(
    path: Path, repository: Path, encoded_hint: str | None = None
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    repo_text = str(repository.resolve())
    try:
        with path.open("rb") as handle:
            sample = handle.read(262_144).decode("utf-8", errors="ignore")
    except OSError:
        return score, reasons
    if repo_text in sample:
        score += 100
        reasons.append("transcript metadata references this repository")
    if encoded_hint and encoded_hint in str(path.parent):
        score += 85
        reasons.append("agent project directory matches this repository")
    if repository.name and repository.name in sample:
        score += 10
        reasons.append("repository name appears in transcript metadata")
    return score, reasons

def recent_jsonl_files(root: Path, limit: int) -> list[tuple[Path, float]]:
    files: list[tuple[Path, float]] = []
    try:
        for path in root.rglob("*.jsonl"):
            try:
                files.append((path, path.stat().st_mtime))
            except OSError:
                continue
    except OSError:
        return []
    return sorted(files, key=lambda item: item[1], reverse=True)[:limit]
