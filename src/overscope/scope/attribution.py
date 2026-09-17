"""Trace each working-tree change back to the agent's own actions.

This is the signal no diff-only reviewer has: the session records which files the
agent actually wrote. A file that changed but was never written by the agent is very
likely the developer's own edit (or another tool's), and Overscope must not blame the
agent for it. Attribution stays deliberately conservative — it only reports
``UNATTRIBUTED`` when the session yields a reliable set of agent-written paths, and
falls back to ``UNKNOWN`` otherwise rather than guessing.
"""

from __future__ import annotations

import re

from overscope.models import Attribution, FileChange, Session
from overscope.sessions.base import shell_commands

_PATCH_FILE = re.compile(
    r"\*\*\*\s+(?:Add|Update|Delete|Move to|Move from)\s+File:\s*(.+)", re.I
)
_PATH_KEYS = ("file_path", "path", "file", "filename", "notebook_path", "target_file", "abspath")
_FS_COMMAND = re.compile(r"\b(?:rm|mv|git\s+rm|git\s+mv)\b([^&|;\n]*)", re.I)

def classify_attribution(
    changes: list[FileChange], session: Session
) -> dict[str, tuple[Attribution, str | None]]:
    written = _agent_written_paths(session)
    have_signal = bool(written)
    result: dict[str, tuple[Attribution, str | None]] = {}
    for change in changes:
        candidates = {_normalize(change.path)}
        if change.old_path:
            candidates.add(_normalize(change.old_path))
        if any(_matches(candidate, written) for candidate in candidates):
            result[change.path] = (Attribution.AGENT, "the agent wrote this file in the session")
        elif have_signal:
            result[change.path] = (
                Attribution.UNATTRIBUTED,
                "changed, but not written by the agent in this session",
            )
        else:
            result[change.path] = (Attribution.UNKNOWN, None)
    return result

def _agent_written_paths(session: Session) -> set[str]:
    paths: set[str] = set()
    for action in session.tool_actions:
        if action.kind == "file_write":
            for key in _PATH_KEYS:
                value = action.input.get(key)
                if isinstance(value, str) and value.strip():
                    paths.add(_normalize(value))
        for value in action.input.values():
            if isinstance(value, str) and "*** " in value:
                paths.update(_patch_targets(value))
        for command in shell_commands(action):
            if "*** " in command:
                paths.update(_patch_targets(command))
            paths.update(_fs_command_targets(command))
    return {path for path in paths if path}

def _patch_targets(text: str) -> set[str]:
    return {_normalize(match.group(1)) for match in _PATCH_FILE.finditer(text)}

def _fs_command_targets(command: str) -> set[str]:
    targets: set[str] = set()
    for match in _FS_COMMAND.finditer(command):
        for token in match.group(1).split():
            cleaned = token.strip("'\"")
            if cleaned and not cleaned.startswith("-") and ("/" in cleaned or "." in cleaned):
                targets.add(_normalize(cleaned))
    return targets

def _normalize(path: str) -> str:
    cleaned = path.strip().strip("`'\"").replace("\\", "/").lower()
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.strip("/")

def _matches(changed: str, written: set[str]) -> bool:
    if not changed:
        return False
    for candidate in written:
        if candidate == changed:
            return True
        if candidate.endswith("/" + changed) or changed.endswith("/" + candidate):
            return True
    return False
