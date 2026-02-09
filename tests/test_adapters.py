"""Adapter parsing tests using saved fixtures (no live network)."""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


# -----------------------------------------------------------------------
# NT adapter
# -----------------------------------------------------------------------

class TestNTAdapter:
    def test_parse_listing_from_fixture(self):
        from weekly_monitor.adapters.nt import NTAdapter

        html = (FIXTURES / "nt_listing.html").read_text(encoding="utf-8")
        adapter = NTAdapter()
        items = adapter.parse_listing(html)

        assert len(items) == 3
        # All URLs should be absolute
        for item in items:
            assert item.url.startswith("http")
        # Check first item
        assert "5G" in items[0].title or "5g" in items[0].title.lower()
        assert items[0].content_hash  # hash was computed

    def test_parse_listing_extracts_dates(self):
        from weekly_monitor.adapters.nt import NTAdapter

        html = (FIXTURES / "nt_listing.html").read_text(encoding="utf-8")
        adapter = NTAdapter()
        items = adapter.parse_listing(html)

        # At least some items should have dates
        dates = [i.date for i in items if i.date]
        assert len(dates) >= 1

    def test_parse_listing_no_duplicate_urls(self):
        from weekly_monitor.adapters.nt import NTAdapter

        html = (FIXTURES / "nt_listing.html").read_text(encoding="utf-8")
        adapter = NTAdapter()
        items = adapter.parse_listing(html)

        urls = [i.url for i in items]
        assert len(urls) == len(set(urls))


# -----------------------------------------------------------------------
# Unitel adapter (API path)
# -----------------------------------------------------------------------

class TestUnitelAdapter:
    def test_parse_api_from_fixture(self):
        from weekly_monitor.adapters.unitel import UnitelAdapter

        data = json.loads((FIXTURES / "unitel_api.json").read_text(encoding="utf-8"))
        adapter = UnitelAdapter()
        items = adapter._parse_api(data)

        assert len(items) == 3
        for item in items:
            assert item.url.startswith("http")
            assert item.title
            assert item.content_hash

    def test_parse_api_strips_html_from_content(self):
        from weekly_monitor.adapters.unitel import UnitelAdapter

        data = json.loads((FIXTURES / "unitel_api.json").read_text(encoding="utf-8"))
        adapter = UnitelAdapter()
        items = adapter._parse_api(data)

        for item in items:
            assert "<p>" not in item.raw_excerpt
            assert "</p>" not in item.raw_excerpt

    def test_parse_api_builds_absolute_urls(self):
        from weekly_monitor.adapters.unitel import UnitelAdapter

        data = json.loads((FIXTURES / "unitel_api.json").read_text(encoding="utf-8"))
        adapter = UnitelAdapter()
        items = adapter._parse_api(data)

        for item in items:
            assert item.url.startswith("https://")

    def test_parse_listing_dispatches_api(self):
        from weekly_monitor.adapters.unitel import UnitelAdapter

        data = json.loads((FIXTURES / "unitel_api.json").read_text(encoding="utf-8"))
        adapter = UnitelAdapter()
        raw = {"source": "api", "data": data}
        items = adapter.parse_listing(raw)
        assert len(items) == 3


# -----------------------------------------------------------------------
# Skytel adapter
# -----------------------------------------------------------------------

class TestSkytelAdapter:
    def test_parse_listing_from_fixture(self):
        from weekly_monitor.adapters.skytel import SkytelAdapter

        html = (FIXTURES / "skytel_listing.html").read_text(encoding="utf-8")
        adapter = SkytelAdapter()
        items = adapter.parse_listing(html)

        assert len(items) == 3
        for item in items:
            assert item.url.startswith("http")
            assert item.title
            assert item.content_hash

    def test_parse_listing_extracts_summaries(self):
        from weekly_monitor.adapters.skytel import SkytelAdapter

        html = (FIXTURES / "skytel_listing.html").read_text(encoding="utf-8")
        adapter = SkytelAdapter()
        items = adapter.parse_listing(html)

        summaries = [i.summary for i in items if i.summary]
        assert len(summaries) >= 1

    def test_parse_listing_no_self_links(self):
        from weekly_monitor.adapters.skytel import SkytelAdapter

        html = (FIXTURES / "skytel_listing.html").read_text(encoding="utf-8")
        adapter = SkytelAdapter()
        items = adapter.parse_listing(html)

        for item in items:
            assert item.url.rstrip("/") != "https://www.skytel.mn/skytel"
            assert item.url.rstrip("/") != "https://www.skytel.mn/news/archiveNew"

    def test_screenshot_targets_include_archive(self):
        from weekly_monitor.adapters.skytel import SkytelAdapter
        from weekly_monitor.core.models import SnapshotItem

        adapter = SkytelAdapter()
        targets = adapter.screenshot_targets([])
        urls = [t["url"] for t in targets]
        assert "https://www.skytel.mn/news/archiveNew" in urls
