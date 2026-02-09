"""Tests for project-root path resolution."""

from __future__ import annotations

import importlib
from pathlib import Path


def test_paths_use_explicit_home_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WEEKLY_MONITOR_HOME", str(tmp_path))
    import weekly_monitor.core.paths as paths
    paths = importlib.reload(paths)

    assert paths.PROJECT_ROOT == tmp_path.resolve()
    assert paths.DATA_ROOT == tmp_path.resolve() / "data"
    assert paths.OUTPUT_ROOT == tmp_path.resolve() / "output"


def test_paths_use_cwd_when_it_looks_like_project(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WEEKLY_MONITOR_HOME", raising=False)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "src" / "weekly_monitor").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)

    import weekly_monitor.core.paths as paths
    paths = importlib.reload(paths)

    assert paths.PROJECT_ROOT == tmp_path.resolve()
