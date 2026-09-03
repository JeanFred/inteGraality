# -*- coding: utf-8 -*-
"""Out-of-band backfill of dashboard page-creation metadata.

It reads dashboard titles the registry reports as missing ``page_created_at``
fetches each page's first revision, and persists the creator/timestamp.
"""

import datetime
import logging

import pywikibot

from .dashboard_registry import DashboardRegistry

logger = logging.getLogger(__name__)


class PageMetadataBackfiller:
    """Fill page_creator / page_created_at for dashboards missing them."""

    def __init__(self, site):
        self.site = site

    @staticmethod
    def _to_utc_datetime_str(timestamp):
        """Render a revision timestamp for the naive-UTC DATETIME column."""
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(datetime.UTC).replace(tzinfo=None)
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")

    def backfill_creation_metadata(self, limit=None):
        """Fill page_creator / page_created_at for rows missing them.

        For each dashboard on this wiki still missing creation metadata,
        read the page's oldest revision (one extra API round-trip) and
        persist the author and timestamp.
        """
        site_hostname = self.site.hostname()
        logger.info("Backfilling page metadata for pages on site %s", site_hostname)
        with DashboardRegistry() as registry:
            rows = registry.list_dashboards_missing_page_metadata(
                site_hostname=site_hostname
            )
        if limit is not None:
            rows = rows[:limit]
        filled = 0
        skipped = 0
        for row in rows:
            page_title = row["page_title"]
            try:
                page = pywikibot.Page(self.site, page_title)
                oldest = page.oldest_revision
                page_created_at = self._to_utc_datetime_str(oldest.timestamp)
                with DashboardRegistry() as registry:
                    registry.update_page_metadata(
                        row["id"], oldest.user, page_created_at
                    )
                filled += 1
            except Exception as e:
                logger.warning(
                    "Failed to backfill page metadata for %s: %s", page_title, e
                )
                skipped += 1
        logger.info("Backfilled %d dashboards (skipped %d failures)", filled, skipped)


def args_parser():
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill page_creator/page_created_at for dashboards "
        "missing them (reads each page's first revision; no SPARQL)"
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="the URL of the wiki to backfill",
        default="https://www.wikidata.org/wiki/",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="backfill at most N dashboards",
    )
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO)
    args = args_parser()
    site = pywikibot.Site(url=args.url)
    PageMetadataBackfiller(site).backfill_creation_metadata(limit=args.limit)


if __name__ == "__main__":
    main()
