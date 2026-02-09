"""Interactive-mode processing tests."""

from __future__ import annotations

from weekly_monitor.adapters.base import SiteAdapter
from weekly_monitor.core.models import SnapshotItem


class _DummyProgress:
    def update(self, *args, **kwargs) -> None:  # pragma: no cover - trivial shim
        return None


class _DetailAdapter(SiteAdapter):
    site_key = "detail"
    site_name = "Detail Site"
    listing_url = "https://example.com/list"

    def __init__(self) -> None:
        self.fetch_detail_calls = 0
        self.parse_detail_calls = 0

    def fetch_listing(self) -> str:
        return "<html></html>"

    def parse_listing(self, raw: str) -> list[SnapshotItem]:
        item = SnapshotItem(url="https://example.com/item-1", title="Item 1", summary="summary")
        item.compute_hash()
        return [item]

    def fetch_detail(self, item: SnapshotItem) -> str:
        self.fetch_detail_calls += 1
        return "<article>updated detail text</article>"

    def parse_detail(self, item: SnapshotItem, raw: str) -> SnapshotItem:
        self.parse_detail_calls += 1
        item.raw_excerpt = "updated detail text"
        item.compute_hash()
        return item


def test_process_site_rich_fetches_details(monkeypatch) -> None:
    from weekly_monitor import interactive

    adapter = _DetailAdapter()
    progress = _DummyProgress()

    monkeypatch.setattr(interactive, "save_snapshot", lambda snapshot: None)
    monkeypatch.setattr(interactive, "load_previous_snapshot", lambda site_key, run_date: None)

    result = interactive._process_site_rich(
        adapter=adapter,
        run_date="2026-02-09",
        run_ts="2026-02-09T00:00:00",
        take_screenshots=False,
        progress=progress,
        task_id=1,
    )

    assert adapter.fetch_detail_calls == 1
    assert adapter.parse_detail_calls == 1
    assert len(result.diff.new_items) == 1
