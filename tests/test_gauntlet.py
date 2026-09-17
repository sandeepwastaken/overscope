from __future__ import annotations

from pathlib import Path

from evaluation.gauntlet import run_gauntlet


def test_advanced_gauntlet(tmp_path: Path) -> None:
    results = run_gauntlet(tmp_path / "advanced-trials")
    failures = [f"{result.name}: {failure}" for result in results for failure in result.failures]
    assert not failures, "\n".join(failures)
    assert sum(result.possible for result in results) >= 40
