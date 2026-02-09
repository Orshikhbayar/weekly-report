"""Project path helpers (data/output rooted in the weekly-updates folder)."""

from __future__ import annotations

import os
from pathlib import Path


def _resolve_project_root() -> Path:
    """Resolve the workspace root for runtime data/output files.

    Priority:
    1. ``WEEKLY_MONITOR_HOME`` env var (explicit override)
    2. Current working directory if it looks like the project root
    3. Repository root derived from this file location
    4. Current working directory fallback
    """
    explicit = os.environ.get("WEEKLY_MONITOR_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    cwd = Path.cwd()
    if (cwd / "pyproject.toml").is_file() and (cwd / "src" / "weekly_monitor").is_dir():
        return cwd.resolve()

    file_path = Path(__file__).resolve()
    # src/weekly_monitor/core/paths.py -> project root is parents[3]
    candidate = file_path.parents[3]
    if (candidate / "pyproject.toml").is_file():
        return candidate

    return cwd.resolve()


PROJECT_ROOT = _resolve_project_root()
DATA_ROOT = PROJECT_ROOT / "data"
OUTPUT_ROOT = PROJECT_ROOT / "output"
