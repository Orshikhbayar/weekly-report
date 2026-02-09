"""Unit tests for the diff engine."""

import pytest

from weekly_monitor.core.diff import diff_snapshots
from weekly_monitor.core.models import Snapshot, SnapshotItem


def _item(url: str, title: str = "t", summary: str = "s", raw: str = "") -> SnapshotItem:
    i = SnapshotItem(url=url, title=title, summary=summary, raw_excerpt=raw)
    i.compute_hash()
    return i


# -----------------------------------------------------------------------
# First run – no previous snapshot
# -----------------------------------------------------------------------

def test_first_run_all_items_are_new():
    current = Snapshot(
        site_key="test",
        items=[_item("https://example.com/1"), _item("https://example.com/2")],
    )
    diff = diff_snapshots(current, None)
    assert len(diff.new_items) == 2
    assert len(diff.updated_items) == 0
    assert diff.new_items[0].url == "https://example.com/1"


# -----------------------------------------------------------------------
# No changes
# -----------------------------------------------------------------------

def test_no_changes():
    items = [_item("https://example.com/1"), _item("https://example.com/2")]
    prev = Snapshot(site_key="test", items=items)
    curr = Snapshot(site_key="test", items=items)
    diff = diff_snapshots(curr, prev)
    assert len(diff.new_items) == 0
    assert len(diff.updated_items) == 0


# -----------------------------------------------------------------------
# New item detected
# -----------------------------------------------------------------------

def test_new_item_detected():
    prev = Snapshot(site_key="test", items=[_item("https://example.com/1")])
    curr = Snapshot(
        site_key="test",
        items=[_item("https://example.com/1"), _item("https://example.com/2")],
    )
    diff = diff_snapshots(curr, prev)
    assert len(diff.new_items) == 1
    assert diff.new_items[0].url == "https://example.com/2"
    assert len(diff.updated_items) == 0


# -----------------------------------------------------------------------
# Updated item detected (title changed)
# -----------------------------------------------------------------------

def test_updated_item_title_changed():
    prev = Snapshot(site_key="test", items=[_item("https://example.com/1", title="old title")])
    curr = Snapshot(site_key="test", items=[_item("https://example.com/1", title="new title")])
    diff = diff_snapshots(curr, prev)
    assert len(diff.new_items) == 0
    assert len(diff.updated_items) == 1
    assert "title" in diff.updated_items[0].changed_fields


# -----------------------------------------------------------------------
# Updated item detected (summary changed)
# -----------------------------------------------------------------------

def test_updated_item_summary_changed():
    prev = Snapshot(site_key="test", items=[_item("https://example.com/1", summary="old summary")])
    curr = Snapshot(site_key="test", items=[_item("https://example.com/1", summary="new summary")])
    diff = diff_snapshots(curr, prev)
    assert len(diff.updated_items) == 1
    assert "summary" in diff.updated_items[0].changed_fields


# -----------------------------------------------------------------------
# Updated item detected (raw_excerpt/content changed)
# -----------------------------------------------------------------------

def test_updated_item_content_changed():
    prev = Snapshot(site_key="test", items=[_item("https://example.com/1", raw="old content")])
    curr = Snapshot(site_key="test", items=[_item("https://example.com/1", raw="new content")])
    diff = diff_snapshots(curr, prev)
    assert len(diff.updated_items) == 1
    assert "content" in diff.updated_items[0].changed_fields


# -----------------------------------------------------------------------
# Mixed: new + updated + unchanged
# -----------------------------------------------------------------------

def test_mixed_diff():
    prev = Snapshot(
        site_key="test",
        items=[
            _item("https://example.com/1", title="same"),
            _item("https://example.com/2", title="old"),
            _item("https://example.com/3", title="removed"),  # removed items are just absent
        ],
    )
    curr = Snapshot(
        site_key="test",
        items=[
            _item("https://example.com/1", title="same"),  # unchanged
            _item("https://example.com/2", title="updated"),  # updated
            _item("https://example.com/4", title="brand new"),  # new
        ],
    )
    diff = diff_snapshots(curr, prev)
    assert len(diff.new_items) == 1
    assert diff.new_items[0].url == "https://example.com/4"
    assert len(diff.updated_items) == 1
    assert diff.updated_items[0].url == "https://example.com/2"


# -----------------------------------------------------------------------
# Site metadata propagated
# -----------------------------------------------------------------------

def test_diff_preserves_site_metadata():
    curr = Snapshot(
        site_key="nt",
        listing_url="https://example.com/news",
        api_url="https://example.com/api",
        items=[],
    )
    diff = diff_snapshots(curr, None)
    assert diff.site_key == "nt"
    assert diff.listing_url == "https://example.com/news"
    assert diff.api_url == "https://example.com/api"
