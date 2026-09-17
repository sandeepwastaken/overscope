from __future__ import annotations

import re
from pathlib import PurePosixPath

from overscope.models import Attribution, Reconciliation, ScopedFile, Session
from overscope.sessions.base import shell_commands

PATH_RE = re.compile(r"(?<![\w@])(?:[\w.@+-]+/)+[\w.@+\-]+(?:\.[A-Za-z0-9]+)?")
TEST_COMMAND_RE = re.compile(
    r"(?:^|\s|[\"'])(?:pytest|tox|nox|cargo\s+test|go\s+test|npm\s+(?:run\s+)?test|"
    r"pnpm\s+test|yarn\s+test|uv\s+run\s+pytest)(?=\s|[\"';,&|)]|$)",
    re.I,
)

def reconcile_claims(session: Session, files: list[ScopedFile]) -> list[Reconciliation]:
    final = session.final_response
    if not final:
        return [
            Reconciliation(
                "Final response",
                "INSUFFICIENT_EVIDENCE",
                "The session has no visible final assistant response to verify.",
            )
        ]
    lowered = final.lower()
    changed = {item.change.path for item in files}
    results: list[Reconciliation] = []

    count = _claimed_file_count(final)
    if count is not None and count != len(changed):
        results.append(
            Reconciliation(
                "Changed-file count",
                "MISMATCH",
                f"The agent described {count} changed file(s), but Git shows {len(changed)}.",
                f"Git paths: {', '.join(sorted(changed)) or 'none'}",
            )
        )

    named = {match.rstrip(".,:;)") for match in PATH_RE.findall(final)}
    named_repo_paths = {path for path in named if path in changed}
    if ("only" in lowered or "just" in lowered) and named_repo_paths:
        omitted = changed - named_repo_paths
        if omitted:
            results.append(
                Reconciliation(
                    "Only named files were changed",
                    "MISMATCH",
                    "The final response uses limiting language but omits changed paths.",
                    ", ".join(sorted(omitted)),
                )
            )

    silent = _undisclosed_changes(session, files)
    if silent:
        preview = ", ".join(silent[:6]) + (" …" if len(silent) > 6 else "")
        results.append(
            Reconciliation(
                "Undisclosed changes",
                "MISMATCH",
                f"The agent wrote {len(silent)} file(s) it never named in its messages.",
                preview,
            )
        )

    claims_tests_added = bool(
        re.search(
            r"(?:added|wrote|created)\s+(?:new\s+)?tests|tests?\s+(?:were\s+)?(?:added|created)",
            lowered,
        )
    )
    has_test_additions = any(
        item.change.kind == "test" and item.change.additions > 0 for item in files
    )
    if claims_tests_added and not has_test_additions:
        results.append(
            Reconciliation(
                "Tests were added",
                "MISMATCH",
                "The final response claims test additions, but no added test diff is present.",
            )
        )

    claims_tests_pass = bool(
        re.search(
            r"(?:all\s+)?tests?\s+(?:now\s+)?pass(?:ed|ing)?|test suite\s+(?:is\s+)?green", lowered
        )
    )
    if claims_tests_pass:
        successful = _successful_test_commands(session)
        if successful:
            results.append(
                Reconciliation(
                    "Tests pass",
                    "SUPPORTED",
                    "The transcript contains a successful test command.",
                    successful[-1],
                )
            )
        else:
            results.append(
                Reconciliation(
                    "Tests pass",
                    "UNVERIFIED",
                    "The final response claims tests pass, but the transcript has no "
                    "captured successful test command.",
                )
            )

    return results

def _undisclosed_changes(session: Session, files: list[ScopedFile]) -> list[str]:
    """Files the agent actually wrote but never named in any visible message.

    Only fires when the agent named at least one changed file — that shows it was
    describing its work by name, so an omission is meaningful rather than just a
    terse summary. Undisclosed edits are the quiet form of scope creep.
    """
    authored = [item for item in files if item.attribution == Attribution.AGENT]
    if not authored:
        return []
    text = "\n".join(session.assistant_messages)
    if not text.strip():
        return []
    named = [item for item in files if _mentions(text, item.change.path)]
    if not named:
        return []
    return sorted(item.change.path for item in authored if not _mentions(text, item.change.path))

def _mentions(text: str, path: str) -> bool:
    if path in text:
        return True
    name = PurePosixPath(path).name
    return len(name) >= 6 and bool(re.search(rf"(?<![\w/]){re.escape(name)}(?![\w])", text))

def _claimed_file_count(text: str) -> int | None:
    patterns = [
        r"(?:changed|modified|updated|touched)\s+(\d+)\s+files?",
        r"(\d+)\s+files?\s+(?:changed|modified|updated|touched)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    return None

def _successful_test_commands(session: Session) -> list[str]:
    commands: list[str] = []
    for action in session.tool_actions:
        if action.success is not True:
            continue
        commands.extend(
            command for command in shell_commands(action) if TEST_COMMAND_RE.search(command)
        )
    return commands
