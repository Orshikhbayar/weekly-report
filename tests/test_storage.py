"""Storage behavior tests."""

from __future__ import annotations

from pathlib import Path

from weekly_monitor.core.models import Snapshot, SnapshotItem


def _snapshot(site_key: str, ts: str, url: str) -> Snapshot:
    item = SnapshotItem(url=url, title="title", summary="summary")
    item.compute_hash()
    return Snapshot(site_key=site_key, run_timestamp=ts, items=[item])


def test_load_previous_snapshot_includes_same_day(monkeypatch, tmp_path: Path) -> None:
    from weekly_monitor.core import storage

    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)

    # Previous run on same day
    storage.save_snapshot(_snapshot("nt", "2026-02-09T08:00:00", "https://a"))
    prev = storage.load_previous_snapshot("nt", "2026-02-09")

    assert prev is not None
    assert prev.items[0].url == "https://a"


def test_load_previous_snapshot_prefers_latest_before_date(monkeypatch, tmp_path: Path) -> None:
    from weekly_monitor.core import storage

    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)

    storage.save_snapshot(_snapshot("nt", "2026-02-08T08:00:00", "https://old"))
    storage.save_snapshot(_snapshot("nt", "2026-02-09T08:00:00", "https://latest"))

    prev = storage.load_previous_snapshot("nt", "2026-02-10")
    assert prev is not None
    assert prev.items[0].url == "https://latest"
