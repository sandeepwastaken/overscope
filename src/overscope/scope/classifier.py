from __future__ import annotations

import re
from pathlib import PurePosixPath

from overscope.models import FileChange, Intent, ScopedFile, ScopeStatus, Session

GENERIC_TOKENS = {"src", "lib", "app", "test", "tests", "index", "main", "config", "docs"}
_UMBRELLA_DIRS = {"", ".", "src", "lib", "app", "source", "pkg", "packages", "internal"}

def _is_module_dir(directory: str) -> bool:
    return directory not in _UMBRELLA_DIRS

def classify_scope(changes: list[FileChange], intent: Intent, session: Session) -> list[ScopedFile]:
    explicit = {_normalize(path) for path in intent.paths}
    avoid = {token for token in intent.avoid if token not in GENERIC_TOKENS}
    intent_tokens = (
        set(intent.keywords) | {token for path in explicit for token in _tokens(path)}
    ) - avoid
    action_paths = _agent_action_paths(session)
    preliminary: list[ScopedFile] = []

    for change in changes:
        path = _normalize(change.path)
        reasons: list[str] = []
        if _explicit_match(path, explicit):
            reasons.append("path is explicitly named in the user instruction")
            preliminary.append(ScopedFile(change, ScopeStatus.IN_SCOPE, reasons))
            continue
        forbidden = sorted(_tokens(path) & avoid)
        if forbidden:
            reasons.append(f"the request asked not to change: {', '.join(forbidden[:3])}")
            preliminary.append(ScopedFile(change, ScopeStatus.OUT_OF_SCOPE, reasons))
            continue
        overlaps = sorted(_tokens(path) & intent_tokens)
        if overlaps:
            reasons.append(f"path matches intent term(s): {', '.join(overlaps[:4])}")
            if path in action_paths:
                reasons.append("session records an agent action on this path")
            preliminary.append(ScopedFile(change, ScopeStatus.IN_SCOPE, reasons))
            continue
        reasons.append("no explicit path or strong filename term matches the instruction")
        if path in action_paths:
            reasons.append(
                "session confirms the agent accessed this path, but not why it was required"
            )
        preliminary.append(ScopedFile(change, ScopeStatus.UNKNOWN, reasons))

    in_scope = [item for item in preliminary if item.scope == ScopeStatus.IN_SCOPE]
    in_stems = {_logical_stem(item.change.path) for item in in_scope}
    in_dirs = {str(PurePosixPath(item.change.path).parent) for item in in_scope}
    clear_intent = bool(explicit or intent_tokens)
    allow_out_of_scope = bool(explicit)

    for item in preliminary:
        if item.scope in {ScopeStatus.IN_SCOPE, ScopeStatus.OUT_OF_SCOPE}:
            continue
        change = item.change
        stem = _logical_stem(change.path)
        parent = str(PurePosixPath(change.path).parent)
        if change.kind == "test" and any(_related_stems(stem, target) for target in in_stems):
            item.scope = ScopeStatus.ADJACENT
            item.reasons = ["test filename corresponds to an in-scope source file"]
        elif parent in in_dirs and _is_module_dir(parent):
            item.scope = ScopeStatus.ADJACENT
            item.reasons = ["file is in the same module directory as an in-scope change"]
        elif change.kind in {"dependency", "lockfile", "config"} and intent.operation in {
            "add",
            "build",
            "create",
        }:
            item.scope = ScopeStatus.ADJACENT
            item.reasons = ["project configuration may support the requested new functionality"]
        elif (
            in_scope
            and clear_intent
            and allow_out_of_scope
            and _separate_area(change.path, [x.change.path for x in in_scope])
        ):
            item.scope = ScopeStatus.OUT_OF_SCOPE
            item.reasons.append(
                "path belongs to a different module from the paths named in the request"
            )
        elif item.scope == ScopeStatus.UNKNOWN and not allow_out_of_scope and in_scope:
            item.reasons.append("request named no concrete path, so scope cannot be confirmed")
    return preliminary

def _agent_action_paths(session: Session) -> set[str]:
    result: set[str] = set()
    for action in session.tool_actions:
        for key in ("file_path", "path", "file", "filename"):
            value = action.input.get(key)
            if isinstance(value, str):
                result.add(_normalize(value))
    return result

def _explicit_match(path: str, explicit: set[str]) -> bool:
    return any(
        path == value or path.endswith(f"/{value}") or value.endswith(f"/{path}")
        for value in explicit
    )

def _normalize(path: str) -> str:
    normalized = path.replace("\\", "/").lower()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")

def _tokens(path: str) -> set[str]:
    tokens: set[str] = set()
    for part in PurePosixPath(path).parts:
        tokens.update(re.split(r"[._-]+", part.lower()))
    return {token for token in tokens if len(token) > 2 and token not in GENERIC_TOKENS}

def _logical_stem(path: str) -> str:
    stem = PurePosixPath(path).stem.lower()
    stem = re.sub(r"^(test_|spec_)", "", stem)
    stem = re.sub(r"(_test|_spec|\.test|\.spec)$", "", stem)
    return stem

def _related_stems(left: str, right: str) -> bool:
    return left == right or left in right or right in left

def _separate_area(path: str, in_scope_paths: list[str]) -> bool:
    candidate = PurePosixPath(path)
    for other_text in in_scope_paths:
        other = PurePosixPath(other_text)
        if candidate.parent == other.parent:
            return False
        if (
            candidate.parts
            and other.parts
            and candidate.parts[0] == other.parts[0]
            and (
                len(candidate.parts) < 3
                or len(other.parts) < 3
                or candidate.parts[1] == other.parts[1]
            )
        ):
            return False
    return True
