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
    parse_json_object,
    probe_file,
    recent_jsonl_files,
    safe_dict,
)

CODEX_META_TYPES = frozenset(
    {
        "turn_context",
        "compacted",
        "token_count",
        "token_usage_record",
        "world_state",
        "inter_agent_communication_metadata",
        "thread_settings_applied",
    }
)
CODEX_KNOWN_ITEMS = frozenset(
    {
        "message",
        "function_call",
        "custom_tool_call",
        "function_call_output",
        "custom_tool_call_output",
        "reasoning",
        "web_search_call",
        "tool_search_call",
        "tool_search_output",
        "agent_message",
    }
)

class CodexAdapter(SessionAdapter):
    kind = AgentKind.CODEX

    def __init__(self, root: Path | None = None) -> None:
        configured = os.environ.get("OVERSCOPE_CODEX_HOME")
        self.root = root or (
            Path(configured).expanduser() if configured else Path.home() / ".codex" / "sessions"
        )

    def candidates(self, repository: Path, limit: int = 80) -> list[SessionCandidate]:
        if not self.root.exists():
            return []
        result: list[SessionCandidate] = []
        for path, modified_at in recent_jsonl_files(self.root, limit):
            score, reasons = probe_file(path, repository)
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
            timestamp = record.get("timestamp")
            if isinstance(timestamp, str):
                session.started_at = session.started_at or timestamp
                session.updated_at = timestamp
            record_type = record.get("type")
            payload = safe_dict(record.get("payload"))
            if record_type in {"session_meta", "session_metadata"}:
                session.id = str(payload.get("id") or payload.get("session_id") or session.id)
                cwd = payload.get("cwd")
                if isinstance(cwd, str):
                    session.cwd = Path(cwd)
            elif record_type == "response_item":
                self._response_item(payload, session, pending, line_number)
            elif record_type == "event_msg":
                self._event_message(payload, session)
            elif record_type not in CODEX_META_TYPES:
                session.unknown_records += 1
            if record_type == "turn_context":
                cwd = payload.get("cwd")
                if isinstance(cwd, str):
                    session.cwd = Path(cwd)
        return session

    @staticmethod
    def _response_item(
        payload: dict[str, Any],
        session: Session,
        pending: dict[str, ToolAction],
        line_number: int,
    ) -> None:
        item_type = payload.get("type")
        if item_type == "message":
            role = payload.get("role")
            texts = content_text(payload.get("content"))
            if role == "user":
                session.user_messages.extend(texts)
            elif role == "assistant":
                session.assistant_messages.extend(texts)
                if texts and payload.get("phase") != "commentary":
                    session.final_message = "\n".join(texts)
        elif item_type in {"function_call", "custom_tool_call"}:
            name = str(payload.get("name") or "unknown")
            raw = payload.get("arguments", payload.get("input"))
            action = ToolAction(
                kind=action_kind(name),
                name=name,
                input=parse_json_object(raw),
                provenance=f"{session.path}:{line_number}",
            )
            session.tool_actions.append(action)
            call_id = payload.get("call_id") or payload.get("id")
            if isinstance(call_id, str):
                pending[call_id] = action
        elif item_type in {"function_call_output", "custom_tool_call_output"}:
            call_id = payload.get("call_id")
            completed_action = pending.get(call_id) if isinstance(call_id, str) else None
            if completed_action:
                output = payload.get("output")
                completed_action.output = str(output)[:10_000] if output is not None else None
                completed_action.success = _output_success(output)
        elif item_type not in CODEX_KNOWN_ITEMS:
            session.unknown_records += 1

    @staticmethod
    def _event_message(payload: dict[str, Any], session: Session) -> None:
        message_type = payload.get("type")
        text = payload.get("message") or payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return
        if message_type in {"user_message", "user"}:
            session.user_messages.append(text)
        elif message_type in {"agent_message", "assistant_message", "assistant"}:
            session.assistant_messages.append(text)
            if payload.get("phase") != "commentary":
                session.final_message = text

def _output_success(output: Any) -> bool | None:
    if output is None:
        return None
    text = str(output).lower()
    if "exit code: 0" in text or '"exit_code":0' in text or '"exit_code": 0' in text:
        return True
    if "exit code:" in text or '"exit_code":' in text:
        return False
    return None
