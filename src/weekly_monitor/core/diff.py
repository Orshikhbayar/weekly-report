"""Diff logic: compare two snapshots and produce new / updated item lists."""

from __future__ import annotations

from weekly_monitor.core.models import DiffItem, SiteDiff, Snapshot, SnapshotItem


def diff_snapshots(
    current: Snapshot,
    previous: Snapshot | None,
) -> SiteDiff:
    """Compare *current* against *previous* (may be None on first run).

    Returns a ``SiteDiff`` with:
    - ``new_items``: URLs not present in previous snapshot.
    - ``updated_items``: URLs present in both but with changed content_hash;
      includes a ``changed_fields`` note.
    """
    result = SiteDiff(
        site_key=current.site_key,
        listing_url=current.listing_url,
        api_url=current.api_url,
    )

    if previous is None:
        # First run – everything is new
        for item in current.items:
            result.new_items.append(_to_diff_item(item))
        return result

    prev_map: dict[str, SnapshotItem] = {i.url: i for i in previous.items}

    for item in current.items:
        if item.url not in prev_map:
            result.new_items.append(_to_diff_item(item))
        else:
            old = prev_map[item.url]
            if item.content_hash != old.content_hash:
                changed = _detect_changed_fields(old, item)
                di = _to_diff_item(item, changed_fields=changed)
                result.updated_items.append(di)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_diff_item(
    item: SnapshotItem,
    changed_fields: list[str] | None = None,
) -> DiffItem:
    return DiffItem(
        url=item.url,
        title=item.title,
        date=item.date,
        summary=item.summary,
        changed_fields=changed_fields or [],
    )


def _detect_changed_fields(old: SnapshotItem, new: SnapshotItem) -> list[str]:
    """Return human-readable list of which fields changed."""
    changed: list[str] = []
    if old.title.strip() != new.title.strip():
        changed.append("title")
    if old.summary.strip() != new.summary.strip():
        changed.append("summary")
    if old.raw_excerpt.strip() != new.raw_excerpt.strip():
        changed.append("content")
    if not changed:
        changed.append("content (hash)")
    return changed
