from __future__ import annotations

from pathlib import Path

from overscope.models import AgentKind, Session, SessionCandidate
from overscope.sessions.base import SessionAdapter
from overscope.sessions.claude import ClaudeAdapter
from overscope.sessions.codex import CodexAdapter


class NoSessionError(RuntimeError):
    pass

class AmbiguousSessionError(RuntimeError):
    def __init__(self, candidates: list[SessionCandidate]) -> None:
        self.candidates = candidates
        choices = "\n".join(f"  {item.agent}: {item.id} ({item.path})" for item in candidates)
        super().__init__(f"Several sessions plausibly match this repository:\n{choices}")

def adapters_for(agent: AgentKind | None = None) -> list[SessionAdapter]:
    available: list[SessionAdapter] = [ClaudeAdapter(), CodexAdapter()]
    return [adapter for adapter in available if agent is None or adapter.kind == agent]

def resolve_session(
    repository: Path,
    *,
    agent: AgentKind | None = None,
    explicit: str | None = None,
    adapters: list[SessionAdapter] | None = None,
) -> Session:
    choices = adapters if adapters is not None else adapters_for(agent)
    if explicit:
        matches: list[tuple[SessionAdapter, Path]] = []
        for adapter in choices:
            path = adapter.find_explicit(explicit)
            if path:
                matches.append((adapter, path))
        if not matches:
            raise NoSessionError(f"No supported session matched {explicit!r}")
        if len(matches) > 1:
            contained = [
                item
                for item in matches
                if item[1].is_relative_to(item[0].root.expanduser().resolve())
            ]
            if len(contained) == 1:
                matches = contained
            exact = [item for item in matches if item[1].stem == explicit]
            matches = exact or matches
        if len(matches) > 1 and len({path for _, path in matches}) == 1:
            parsed_sessions: list[Session] = []
            for adapter, path in matches:
                try:
                    parsed_sessions.append(_require_usable(adapter.parse(path)))
                except NoSessionError:
                    continue
            if parsed_sessions:
                return max(parsed_sessions, key=_session_signal)
            raise NoSessionError(
                f"Session {matches[0][1]} matched the repository but no supported adapter "
                "found usable visible messages or tool activity. The transcript schema may "
                "be unsupported."
            )
        adapter, path = max(matches, key=lambda item: item[1].stat().st_mtime)
        selected = adapter.parse(path)
        return _require_usable(selected)

    candidates: list[tuple[SessionAdapter, SessionCandidate]] = []
    for adapter in choices:
        candidates.extend((adapter, candidate) for candidate in adapter.candidates(repository))
    candidates.sort(key=lambda item: (item[1].score, item[1].modified_at), reverse=True)
    related = [item for item in candidates if item[1].score >= 80]
    if not related:
        roots = ", ".join(str(adapter.root) for adapter in choices)
        raise NoSessionError(
            f"No session confidently matched {repository}. Searched: {roots}. "
            "Use --session PATH to select one explicitly."
        )
    top_adapter, top = related[0]
    if len(related) > 1:
        second = related[1][1]
        same_time = abs(top.modified_at - second.modified_at) < 1
        if top.score == second.score and same_time and top.agent != second.agent:
            raise AmbiguousSessionError([top, second])
    return _require_usable(top_adapter.parse(top.path))

def _require_usable(session: Session) -> Session:
    if session.user_messages or session.assistant_messages or session.tool_actions:
        return session
    detail = (
        f" ({session.malformed_records} malformed record(s))" if session.malformed_records else ""
    )
    raise NoSessionError(
        f"Session {session.path} matched the repository but contained no usable visible "
        f"messages or tool activity{detail}. The transcript schema may be unsupported."
    )

def _session_signal(session: Session) -> int:
    return (
        len(session.user_messages) * 4
        + len(session.assistant_messages) * 3
        + len(session.tool_actions) * 2
        + (5 if session.cwd else 0)
    )
