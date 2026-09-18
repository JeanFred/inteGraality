"""Backfill dashboard_runs from InteGraalityBot's edit history via the API.

One paginated prop=revisions query per dashboard
(rvuser=bot,rvprop=ids|timestamp|comment|content, rvlimit=50)
returns, in each response, both the edit summary (=> trigger/engine/elapsed)
and the wikitext content (=> the totals-row counts), so a single pass
fills every dashboard_runs column the live path would
(entity_total/grouping_count/column_count included).

Reads the dashboard set from the registry, records each revision as an
idempotent OK run (INSERT IGNORE on the revision), commits per dashboard, and
isolates per-dashboard failures so one bad page never kills the batch. Fetching
is throttled and maxlag-aware; the summary parser and the wikitext totals-row
parser handle both the modern {{Integraality cell|...|grouping=X}} format and
the pre-Nov-2019 {{Coloured cell|pct|count}} era.
"""

import argparse
import datetime
import logging
import re
from dataclasses import dataclass

import pywikibot
from pywikibot.data import api

from .dashboard_registry import DashboardRegistry, RunResult
from .report_parser import ReportParser

logger = logging.getLogger(__name__)

BOT_USERNAME = "InteGraalityBot"

# --- Edit-summary parsing -------------------------------------------------
# Cron summaries start with this; anything else is a web update.
CRON_SUMMARY_PREFIX = "Weekly update of"
# No engine named => pre-QLever run, i.e. WDQS. Matches WdqsSparqlQueryEngine.name.
DEFAULT_ENGINE = "Wikidata Query Service"
# " using <engine>" and its trailing " (<n>s)" are both optional.
_SUMMARY_TAIL_RE = re.compile(
    r"\busing\s+(?P<engine>.+?)(?:\s+\((?P<seconds>\d+)s\))?$"
)


@dataclass(frozen=True)
class ParsedSummary:
    """Run fields recoverable from one edit summary."""

    trigger_source: str
    sparql_engine: str | None = DEFAULT_ENGINE
    duration_ms: int | None = None


def parse_edit_summary(summary):
    """Parse trigger/engine/elapsed out of a bot edit summary."""
    summary = (summary or "").strip()
    trigger_source = "CRON" if summary.startswith(CRON_SUMMARY_PREFIX) else "WEB"

    sparql_engine = DEFAULT_ENGINE
    duration_ms = None
    match = _SUMMARY_TAIL_RE.search(summary)
    if match:
        sparql_engine = match.group("engine").strip() or DEFAULT_ENGINE
        seconds = match.group("seconds")
        if seconds is not None:
            duration_ms = int(seconds) * 1000

    return ParsedSummary(
        trigger_source=trigger_source,
        sparql_engine=sparql_engine,
        duration_ms=duration_ms,
    )


# --- API fetch ------------------------------------------------------------

# Revisions requested per prop=revisions page. The API enforces rvlimit<=50
# whenever rvprop=content, so 50 is the effective ceiling for our content query
# (requesting more is silently clamped). Even 50 huge revisions can exceed the
# 12 MB response cap and get truncated — backfill_dashboard re-fetches any
# revision that comes back unparseable rather than shrinking every batch to
# chase the rare pathological dashboard. pywikibot handles
# continuation/throttle/maxlag.
REV_BATCH = 50


def parse_totals_from_wikitext(wikitext):
    """Return (entity_total, grouping_count, column_count) for a revision's
    rendered dashboard table, or (None, None, None) when not recoverable.

    Thin wrapper over ReportParser.shape — the parser handles both the modern
    Integraality-cell and old Coloured-cell eras, the higher-grouping totals
    prefix, linked count cells, and excludes the No-grouping/config rows.
    """
    return ReportParser().parse(wikitext).shape


def _slot_content(rev):
    """Extract a revision's main-slot wikitext. pywikibot uses formatversion 1,
    so slot content is under the "*" key."""
    return rev.get("slots", {}).get("main", {}).get("*", "")


class ApiRunsBackfiller:
    """Backfill dashboard_runs (metadata + counts) via the MediaWiki API.

    One paginated prop=revisions query per dashboard, filtered server-side to
    the bot (rvuser) and pulling content (rvprop=...|content, rvslots=main), so
    each response carries both the summary (=> trigger/engine/elapsed) and the
    wikitext (=> the totals-row counts). Fetching uses pywikibot's
    api.PropertyGenerator, which handles continuation, throttling, maxlag and
    the User-Agent per Wikimedia policy.
    """

    def __init__(self, site, registry=None):
        self.site = site
        self._registry = registry

    @property
    def site_hostname(self):
        return self.site.hostname()

    def _bot_revisions(self, title):
        """Yield (revid, timestamp, comment, content) for the bot's revisions.

        Server-side rvuser filter (so we never download human edits), content
        pulled in the same response. Continuation/throttle/maxlag are handled by
        the generator; it yields one dict per page, each carrying the revisions.
        """
        generator = api.PropertyGenerator(
            "revisions",
            site=self.site,
            parameters={
                "titles": title,
                "rvlimit": REV_BATCH,
                "rvprop": "ids|timestamp|comment|content",
                "rvslots": "main",
                "rvuser": BOT_USERNAME,
            },
        )
        for page in generator:
            for rev in page.get("revisions", []):
                yield (
                    rev["revid"],
                    rev["timestamp"],
                    rev.get("comment", ""),
                    _slot_content(rev),
                )

    def _fetch_revision_content(self, revid):
        """Re-fetch a single revision's content by revid (rvlimit=1).

        Used to recover a revision whose content was truncated in a batched
        response (the 12 MB cap): one revision alone fits comfortably. Returns
        the wikitext, or "" if the revision is gone.
        """
        generator = api.PropertyGenerator(
            "revisions",
            site=self.site,
            parameters={
                "revids": revid,
                "rvprop": "content",
                "rvslots": "main",
            },
        )
        for page in generator:
            for rev in page.get("revisions", []):
                return _slot_content(rev)
        return ""

    @staticmethod
    def _timestamp_to_datetime_str(iso_timestamp):
        """ISO-8601 API timestamp (e.g. 2026-02-13T01:18:34Z) -> naive-UTC
        DATETIME string, parsed (not string-munged) so a malformed value fails
        loud rather than writing garbage."""
        parsed = datetime.datetime.strptime(iso_timestamp, "%Y-%m-%dT%H:%M:%SZ")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    def _counts_for_revision(self, revid, content):
        """Parse (entity_total, grouping_count, column_count) from a revision's
        content, re-fetching the revision alone if a batched fetch truncated it.

        A non-empty content that parses to all-None means the totals row was cut
        off — almost always the 12 MB response cap on a batch of huge revisions.
        Re-fetching the single revision gets complete content. If it *still*
        won't parse, the counts stay None (logged) — an acceptable NULL row.
        """
        shape = parse_totals_from_wikitext(content)
        if content and shape == (None, None, None):
            logger.warning(
                "Revision %s parsed to no counts (likely truncated); re-fetching",
                revid,
            )
            shape = parse_totals_from_wikitext(self._fetch_revision_content(revid))
            if shape == (None, None, None):
                logger.warning(
                    "Revision %s still unparseable after re-fetch; counts NULL",
                    revid,
                )
        return shape

    def backfill_dashboard(self, registry, title, dashboard_id, wiki_id):
        """Backfill every bot run of one dashboard. Returns count inserted.

        Records via the resolved path (ids known from the registry), so no
        wiki/page/dashboard re-resolution per revision and no pywikibot call.
        """
        inserted = 0
        for revid, timestamp, comment, content in self._bot_revisions(title):
            parsed = parse_edit_summary(comment)
            entity_total, grouping_count, column_count = self._counts_for_revision(
                revid, content
            )
            run = RunResult.ok(
                revision_id=revid,
                trigger_source=parsed.trigger_source,
                duration_ms=parsed.duration_ms,
                sparql_engine=parsed.sparql_engine,
                entity_total=entity_total,
                grouping_count=grouping_count,
                column_count=column_count,
            )
            finished_at = self._timestamp_to_datetime_str(timestamp)
            if registry.record_resolved_backfilled_run(
                dashboard_id, wiki_id, run, finished_at
            ):
                inserted += 1
        registry.conn.commit()
        return inserted

    def backfill_runs(self, limit=None):
        """Backfill runs for this wiki's registered dashboards via the API.

        One paginated rvuser+content query per dashboard fills metadata +
        counts. A failing dashboard is logged and skipped so one bad page never
        kills the batch. ``limit`` caps the number of dashboards processed.
        Returns the total runs inserted.
        """
        registry = self._registry or DashboardRegistry()
        owns_registry = self._registry is None
        try:
            dashboards = registry.list_dashboards_for_backfill(self.site_hostname)
            if not dashboards:
                logger.info(
                    "No dashboards on %s; nothing to backfill", self.site_hostname
                )
                return 0
            if limit is not None:
                dashboards = dashboards[:limit]

            logger.info(
                "Backfilling runs for %d dashboards on %s",
                len(dashboards),
                self.site_hostname,
            )
            inserted = 0
            failed = 0
            for i, (title, dashboard_id, wiki_id) in enumerate(dashboards, start=1):
                logger.info("[%d/%d] Backfilling %s...", i, len(dashboards), title)
                try:
                    n = self.backfill_dashboard(registry, title, dashboard_id, wiki_id)
                    inserted += n
                    logger.info(
                        "[%d/%d] %s: +%d runs (%d total)",
                        i,
                        len(dashboards),
                        title,
                        n,
                        inserted,
                    )
                except Exception as e:
                    failed += 1
                    logger.warning("Failed to backfill %s: %s", title, e)
            logger.info(
                "Done on %s: inserted %d runs, %d dashboards failed",
                self.site_hostname,
                inserted,
                failed,
            )
            return inserted
        finally:
            if owns_registry:
                registry.close()


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Backfill dashboard_runs (metadata + counts) from "
        "InteGraalityBot's edit history via the MediaWiki API"
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="https://www.wikidata.org/wiki/",
        help="the URL of the wiki to backfill",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="process at most N dashboards",
    )
    args = parser.parse_args()
    site = pywikibot.Site(url=args.url)
    ApiRunsBackfiller(site).backfill_runs(limit=args.limit)


if __name__ == "__main__":
    main()
