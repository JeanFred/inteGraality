# -*- coding: utf-8  -*-
"""Unit tests for page_metadata_backfiller.py."""

import argparse
import datetime
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

import pywikibot

from ..page_metadata_backfiller import PageMetadataBackfiller, main


def _site(hostname="www.wikidata.org"):
    site = MagicMock()
    site.hostname.return_value = hostname
    return site


class TestBackfill(unittest.TestCase):
    """backfill_creation_metadata() reads each page's oldest revision and
    persists the creator/timestamp, skipping pages that fail."""

    def _oldest_revision(self, user="Alice", timestamp=None):
        if timestamp is None:
            # A real pywikibot Timestamp (not a plain datetime): it overrides
            # isoformat()/str() to append 'Z', so this fixture is what guards
            # the DATETIME-format conversion against regressions.
            timestamp = pywikibot.Timestamp.fromISOformat("2020-01-02T03:04:05Z")
        revision = MagicMock()
        revision.user = user
        revision.timestamp = timestamp
        return revision

    @patch("integraality.page_metadata_backfiller.pywikibot.Page")
    @patch("integraality.page_metadata_backfiller.DashboardRegistry")
    def test_backfills_creator_and_timestamp(self, mock_registry_cls, mock_page_cls):
        registry = mock_registry_cls.return_value.__enter__.return_value
        registry.list_dashboards_missing_page_metadata.return_value = [
            {
                "id": 11,
                "page_title": "Wikidata:Foo",
                "site_hostname": "www.wikidata.org",
            }
        ]
        page = MagicMock()
        page.oldest_revision = self._oldest_revision()
        mock_page_cls.return_value = page

        PageMetadataBackfiller(_site()).backfill_creation_metadata()

        registry.update_page_metadata.assert_called_once_with(
            11, "Alice", "2020-01-02 03:04:05"
        )

    @patch("integraality.page_metadata_backfiller.pywikibot.Page")
    @patch("integraality.page_metadata_backfiller.DashboardRegistry")
    def test_filters_by_own_wiki(self, mock_registry_cls, mock_page_cls):
        """The registry query is scoped to this backfiller's own wiki."""
        registry = mock_registry_cls.return_value.__enter__.return_value
        registry.list_dashboards_missing_page_metadata.return_value = []

        PageMetadataBackfiller(_site("meta.wikimedia.org")).backfill_creation_metadata()

        registry.list_dashboards_missing_page_metadata.assert_called_once_with(
            site_hostname="meta.wikimedia.org"
        )

    @patch("integraality.page_metadata_backfiller.pywikibot.Page")
    @patch("integraality.page_metadata_backfiller.DashboardRegistry")
    def test_skips_failing_page_and_continues(self, mock_registry_cls, mock_page_cls):
        registry = mock_registry_cls.return_value.__enter__.return_value
        registry.list_dashboards_missing_page_metadata.return_value = [
            {"id": 1, "page_title": "Bad", "site_hostname": "www.wikidata.org"},
            {"id": 2, "page_title": "Good", "site_hostname": "www.wikidata.org"},
        ]
        bad_page = MagicMock()
        type(bad_page).oldest_revision = PropertyMock(side_effect=Exception("deleted"))
        good_page = MagicMock()
        good_page.oldest_revision = self._oldest_revision(user="Bob")
        mock_page_cls.side_effect = [bad_page, good_page]

        PageMetadataBackfiller(_site()).backfill_creation_metadata()  # must not raise

        # Only the good page was persisted; the batch continued past the bad one.
        registry.update_page_metadata.assert_called_once_with(
            2, "Bob", "2020-01-02 03:04:05"
        )

    @patch("integraality.page_metadata_backfiller.pywikibot.Page")
    @patch("integraality.page_metadata_backfiller.DashboardRegistry")
    def test_respects_limit(self, mock_registry_cls, mock_page_cls):
        registry = mock_registry_cls.return_value.__enter__.return_value
        registry.list_dashboards_missing_page_metadata.return_value = [
            {"id": i, "page_title": f"P{i}", "site_hostname": "www.wikidata.org"}
            for i in range(5)
        ]
        page = MagicMock()
        page.oldest_revision = self._oldest_revision()
        mock_page_cls.return_value = page

        PageMetadataBackfiller(_site()).backfill_creation_metadata(limit=2)

        self.assertEqual(registry.update_page_metadata.call_count, 2)


class TestToUtcDatetimeStr(unittest.TestCase):
    """The naive-UTC DATETIME format conversion and its UTC invariant."""

    def test_naive_timestamp_formatted_without_t_or_z(self):
        # A real pywikibot Timestamp (naive UTC) — the type that hits the DB.
        ts = pywikibot.Timestamp.fromISOformat("2013-07-23T11:24:39Z")
        self.assertEqual(
            PageMetadataBackfiller._to_utc_datetime_str(ts), "2013-07-23 11:24:39"
        )

    def test_tz_aware_timestamp_converted_to_utc(self):
        """A tz-aware timestamp is converted to UTC, not formatted as-is —
        otherwise wall-clock local time would be written into the UTC column."""
        # 08:24:39 at +05:00 is 03:24:39 UTC.
        aware = datetime.datetime(
            2013,
            7,
            23,
            8,
            24,
            39,
            tzinfo=datetime.timezone(datetime.timedelta(hours=5)),
        )
        self.assertEqual(
            PageMetadataBackfiller._to_utc_datetime_str(aware), "2013-07-23 03:24:39"
        )

    def test_microseconds_dropped(self):
        ts = datetime.datetime(2013, 7, 23, 11, 24, 39, 123456, tzinfo=datetime.UTC)
        self.assertEqual(
            PageMetadataBackfiller._to_utc_datetime_str(ts), "2013-07-23 11:24:39"
        )


class TestMain(unittest.TestCase):
    def setUp(self):
        patcher1 = patch(
            "integraality.page_metadata_backfiller.PageMetadataBackfiller",
            autospec=True,
        )
        self.mock_backfiller = patcher1.start()
        self.addCleanup(patcher1.stop)

        patcher2 = patch("integraality.page_metadata_backfiller.pywikibot.Site")
        self.mock_site = patcher2.start()
        self.addCleanup(patcher2.stop)

        patcher3 = patch("argparse.ArgumentParser.parse_args", autospec=True)
        self.mock_args = patcher3.start()
        self.addCleanup(patcher3.stop)

    def test_main_builds_site_and_backfills(self):
        self.mock_args.return_value = argparse.Namespace(
            url="https://www.wikidata.org/wiki/", limit=None
        )
        main()
        self.mock_site.assert_called_once_with(url="https://www.wikidata.org/wiki/")
        self.mock_backfiller.assert_called_once_with(self.mock_site.return_value)
        self.mock_backfiller.return_value.backfill_creation_metadata.assert_called_once_with(
            limit=None
        )

    def test_main_passes_limit(self):
        self.mock_args.return_value = argparse.Namespace(
            url="https://www.wikidata.org/wiki/", limit=5
        )
        main()
        self.mock_backfiller.return_value.backfill_creation_metadata.assert_called_once_with(
            limit=5
        )
