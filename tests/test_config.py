from __future__ import annotations

from pathlib import Path

from overscope.config import load_config
from overscope.models import Severity


def test_config_loads_and_reports_invalid_values(tmp_path: Path) -> None:
    (tmp_path / ".overscope.toml").write_text(
        """
[overscope]
ignored_rules = ["code.todo_added"]
ignored_paths = ["vendor/**"]
sensitive_paths = ["^infra/", "["]

[overscope.severity_overrides]
"code.debug_statement" = "INFO"
"bad" = "urgent"
""",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.ignored_rules == {"code.todo_added"}
    assert config.path_ignored("vendor/pkg/file.py")
    assert config.sensitive_paths == ["^infra/"]
    assert config.severity_overrides["code.debug_statement"] == Severity.INFO
    assert len(config.warnings) == 2
