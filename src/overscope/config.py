from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from overscope.models import Severity


@dataclass(slots=True)
class Config:
    ignored_rules: set[str] = field(default_factory=set)
    severity_overrides: dict[str, Severity] = field(default_factory=dict)
    ignored_paths: list[str] = field(default_factory=list)
    trusted_paths: list[str] = field(default_factory=list)
    sensitive_paths: list[str] = field(default_factory=list)
    preferred_agent: str | None = None
    warnings: list[str] = field(default_factory=list)

    def path_ignored(self, path: str) -> bool:
        return any(fnmatch(path, pattern) for pattern in self.ignored_paths)

    def path_trusted(self, path: str) -> bool:
        return any(fnmatch(path, pattern) for pattern in self.trusted_paths)

def load_config(repository: Path) -> Config:
    path = repository / ".overscope.toml"
    if not path.is_file():
        return Config()
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Config(warnings=[f"Could not load {path}: {exc}"])
    section = raw.get("overscope", raw)
    if not isinstance(section, dict):
        return Config(warnings=[f"Expected a table in {path}"])
    sensitive_paths = _string_list(section.get("sensitive_paths"))
    config = Config(
        ignored_rules=_string_set(section.get("ignored_rules")),
        ignored_paths=_string_list(section.get("ignored_paths")),
        trusted_paths=_string_list(section.get("trusted_paths")),
        sensitive_paths=[],
        preferred_agent=section.get("preferred_agent")
        if isinstance(section.get("preferred_agent"), str)
        else None,
    )
    for pattern in sensitive_paths:
        try:
            re.compile(pattern)
        except re.error as exc:
            config.warnings.append(f"Ignored invalid sensitive path regex {pattern!r}: {exc}")
        else:
            config.sensitive_paths.append(pattern)
    overrides = section.get("severity_overrides", {})
    if isinstance(overrides, dict):
        for rule_id, value in overrides.items():
            try:
                config.severity_overrides[str(rule_id)] = Severity(str(value).upper())
            except ValueError:
                config.warnings.append(f"Ignored invalid severity override for {rule_id}: {value}")
    return config

def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []

def _string_set(value: Any) -> set[str]:
    return set(_string_list(value))
