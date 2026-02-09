"""Snapshot persistence – JSON files under <project>/data/<site_key>/."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from weekly_monitor.core.models import Snapshot
from weekly_monitor.core.paths import DATA_ROOT


def _site_dir(site_key: str) -> Path:
    d = DATA_ROOT / site_key
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_snapshot(snapshot: Snapshot) -> Path:
    """Persist a snapshot; returns the written path."""
    ts = snapshot.run_timestamp[:10]  # YYYY-MM-DD
    path = _site_dir(snapshot.site_key) / f"{ts}.json"
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_snapshot(site_key: str, run_date: str) -> Optional[Snapshot]:
    """Load a specific date's snapshot, or None."""
    path = _site_dir(site_key) / f"{run_date}.json"
    if not path.exists():
        return None
    return Snapshot.model_validate_json(path.read_text(encoding="utf-8"))


def load_previous_snapshot(site_key: str, current_date: str) -> Optional[Snapshot]:
    """Find the most recent snapshot *before* current_date."""
    site_dir = _site_dir(site_key)
    files = sorted(site_dir.glob("*.json"), reverse=True)
    for f in files:
        name = f.stem  # YYYY-MM-DD
        if name < current_date:
            return Snapshot.model_validate_json(f.read_text(encoding="utf-8"))
    return None


def list_snapshots(site_key: str) -> list[str]:
    """Return sorted list of snapshot dates for a site."""
    site_dir = _site_dir(site_key)
    return sorted(f.stem for f in site_dir.glob("*.json"))
