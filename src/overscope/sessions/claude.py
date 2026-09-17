from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from overscope.models import AgentKind, Session, SessionCandidate, ToolAction
from overscope.sessions.base import (
    SessionAdapter,
    action_kind,
    content_text,
    jsonl_records,
    probe_file,
    recent_jsonl_files,
    safe_dict,
)

CLAUDE_META_TYPES = frozenset(
    {
        "progress",
        "summary",
        "system",
        "queue-operation",
        "file-history-snapshot",
        "file-history-delta",
        "attachment",
        "custom-title",
        "ai-title",
        "atis-latch",
        "mode",
        "last-prompt",
        "bridge-session",
    }
)

class ClaudeAdapter(SessionAdapter):
    kind = AgentKind.CLAUDE

    def __init__(self, root: Path | None = None) -> None:
        configured = os.environ.get("OVERSCOPE_CLAUDE_HOME")
        self.root = root or (
            Path(configured).expanduser() if configured else Path.home() / ".claude" / "projects"
        )

    def candidates(self, repository: Path, limit: int = 80) -> list[SessionCandidate]:
        if not self.root.exists():
            return []
        encoded = str(repository.resolve()).replace("/", "-")
        result: list[SessionCandidate] = []
        for path, modified_at in recent_jsonl_files(self.root, limit):
            score, reasons = probe_file(path, repository, encoded)
            result.append(SessionCandidate(path.stem, self.kind, path, modified_at, score, reasons))
        return sorted(result, key=lambda item: (item.score, item.modified_at), reverse=True)

    def parse(self, path: Path) -> Session:
        session = Session(id=path.stem, agent=self.kind, path=path)
        pending: dict[str, ToolAction] = {}
        for line_number, record in jsonl_records(path):
            if record is None:
                session.malformed_records += 1
                session.warnings.append(f"Ignored malformed JSONL record at line {line_number}")
                continue
            session.id = str(record.get("sessionId") or record.get("session_id") or session.id)
            cwd = record.get("cwd") or record.get("projectPath")
            if isinstance(cwd, str):
                session.cwd = Path(cwd)
            timestamp = record.get("timestamp")
            if isinstance(timestamp, str):
                session.started_at = session.started_at or timestamp
                session.updated_at = timestamp

            record_type = record.get("type")
            message = safe_dict(record.get("message"))
            role = message.get("role") or (
                record_type if record_type in {"user", "assistant"} else None
            )
            content = message.get("content", record.get("content"))
            if role == "user":
                texts = content_text(content)
                session.user_messages.extend(texts)
                self._capture_tool_results(content, pending)
            elif role == "assistant":
                texts = content_text(content)
                session.assistant_messages.extend(texts)
                if texts:
                    session.final_message = "\n".join(texts)
                self._capture_tools(content, session, pending, line_number)
            elif record_type not in CLAUDE_META_TYPES:
                session.unknown_records += 1
        return session

    @staticmethod
    def _capture_tools(
        content: Any, session: Session, pending: dict[str, ToolAction], line_number: int
    ) -> None:
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = str(block.get("name") or "unknown")
            raw_input = block.get("input")
            action = ToolAction(
                kind=action_kind(name),
                name=name,
                input=raw_input if isinstance(raw_input, dict) else {},
                provenance=f"{session.path}:{line_number}",
            )
            session.tool_actions.append(action)
            tool_id = block.get("id")
            if isinstance(tool_id, str):
                pending[tool_id] = action

    @staticmethod
    def _capture_tool_results(content: Any, pending: dict[str, ToolAction]) -> None:
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            tool_id = block.get("tool_use_id")
            action = pending.get(tool_id) if isinstance(tool_id, str) else None
            if action is None:
                continue
            output = block.get("content")
            if isinstance(output, str):
                action.output = output[:10_000]
            else:
                action.output = "\n".join(content_text(output))[:10_000]
            action.success = not bool(block.get("is_error", False))
