from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conftest import init_repo, write_jsonl
from typer.testing import CliRunner

from overscope.cli import app

runner = CliRunner()

def _repo_with_session(tmp_path: Path, monkeypatch) -> Path:
    repo = init_repo(tmp_path / "repo")
    (repo / "keep.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "test_keep.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "test_keep.py"], check=True)

    claude_root = tmp_path / "claude"
    write_jsonl(
        claude_root / "proj" / "s.jsonl",
        [
            {
                "type": "user",
                "sessionId": "s",
                "cwd": str(repo),
                "message": {"role": "user", "content": "Update keep.py in this repo."},
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": "t", "name": "Bash",
                         "input": {"command": "rm test_keep.py"}},
                    ],
                },
            },
        ],
    )
    monkeypatch.setenv("OVERSCOPE_CLAUDE_HOME", str(claude_root))
    monkeypatch.setenv("OVERSCOPE_CODEX_HOME", str(tmp_path / "no-codex"))
    monkeypatch.chdir(repo)
    return repo

def test_fail_on_high_exits_nonzero(tmp_path: Path, monkeypatch) -> None:
    _repo_with_session(tmp_path, monkeypatch)
    result = runner.invoke(app, ["--fail-on", "high"])
    assert result.exit_code == 1

def test_default_run_exits_zero(tmp_path: Path, monkeypatch) -> None:
    _repo_with_session(tmp_path, monkeypatch)
    result = runner.invoke(app, [])
    assert result.exit_code == 0

def test_json_output_is_valid_and_ansi_free(tmp_path: Path, monkeypatch) -> None:
    _repo_with_session(tmp_path, monkeypatch)
    result = runner.invoke(app, ["--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"]
    assert "\x1b" not in result.stdout
    assert any(f["attribution"] == "AGENT" for f in payload["files"])

def test_doctor_runs(tmp_path: Path, monkeypatch) -> None:
    _repo_with_session(tmp_path, monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "OVERSCOPE DOCTOR" in result.stdout

def test_rules_lists_checks(tmp_path: Path, monkeypatch) -> None:
    result = runner.invoke(app, ["rules"])
    assert result.exit_code == 0
    assert "dangerous_command" in result.stdout
