"""Abstract base class for site adapters."""

from __future__ import annotations

import abc
from typing import Any

from weekly_monitor.core.models import Snapshot, SnapshotItem


class SiteAdapter(abc.ABC):
    """Each target site implements this interface."""

    site_key: str  # e.g. "nt", "unitel", "skytel"
    site_name: str  # Human-readable, e.g. "NT (National Telecom)"
    listing_url: str  # Primary listing page used for discovery
    api_url: str = ""  # API endpoint if applicable

    # ------------------------------------------------------------------
    # Required methods
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def fetch_listing(self) -> Any:
        """Fetch raw listing data (HTML string, JSON, etc.)."""
        ...

    @abc.abstractmethod
    def parse_listing(self, raw: Any) -> list[SnapshotItem]:
        """Parse raw listing data into a list of SnapshotItem."""
        ...

    # ------------------------------------------------------------------
    # Optional methods (override when needed)
    # ------------------------------------------------------------------

    def fetch_detail(self, item: SnapshotItem) -> Any:
        """Fetch detail page for a single item. Return raw HTML or None."""
        return None

    def parse_detail(self, item: SnapshotItem, raw: Any) -> SnapshotItem:
        """Enrich *item* with detail-page content. Return mutated item."""
        return item

    def screenshot_targets(self, new_items: list[SnapshotItem]) -> list[dict]:
        """Return screenshot targets: list of {url, filename, label}.

        Default: listing page + up to 10 new-item detail pages.
        """
        targets: list[dict] = [
            {
                "url": self.listing_url,
                "filename": "listing.png",
                "label": f"{self.site_name} – listing page",
            }
        ]
        for idx, item in enumerate(new_items[:9]):
            targets.append(
                {
                    "url": item.url,
                    "filename": f"new_{idx}.png",
                    "label": item.title or item.url,
                }
            )
        return targets

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def build_snapshot(self, items: list[SnapshotItem], run_ts: str) -> Snapshot:
        """Wrap items into a Snapshot."""
        return Snapshot(
            site_key=self.site_key,
            run_timestamp=run_ts,
            listing_url=self.listing_url,
            api_url=self.api_url,
            items=items,
        )
