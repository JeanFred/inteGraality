"""Unit tests for the runs backfiller.

Fully testable with pywikibot's api.PropertyGenerator mocked — no replica, no
Docker, no network.
"""

import unittest
from unittest.mock import MagicMock, patch

from ..runs_backfiller import (
    REV_BATCH,
    ApiRunsBackfiller,
    parse_totals_from_wikitext,
)

_CURRENT_TABLE = """\
{| class="wikitable sortable"
|-
! Name
! Count
|-
| Germany
| 500
| {{Integraality cell|80|400|column=P21|grouping=Q183}}
| {{Integraality cell|60|300|column=P569|grouping=Q183}}
|- class="sortbottom"
| '''Totals''' <small>(all items)</small>
| 39163
| {{Integraality cell|100|39163|column=P21}}
| {{Integraality cell|100|39163|column=P569}}
|}
"""

_OLD_TABLE = """\
{| class="wikitable sortable"
|-
! Name
! Count
|- class="sortbottom"
| '''Totals''' <small>(all items)</small>:
| 1,234
| {{Coloured cell|100|1234}}
|}
"""


class TestParseTotals(unittest.TestCase):
    """parse_totals_from_wikitext delegates to ReportParser.shape; the parser's
    own era/grouping-type coverage lives in test_report_parser.py. These just
    confirm the delegation and the empty guard."""

    def test_delegates_to_report_parser_shape(self):
        self.assertEqual(parse_totals_from_wikitext(_CURRENT_TABLE), (39163, 1, 2))
        self.assertEqual(parse_totals_from_wikitext(_OLD_TABLE), (1234, None, 1))

    def test_empty_or_none(self):
        self.assertEqual(parse_totals_from_wikitext(""), (None, None, None))
        self.assertEqual(parse_totals_from_wikitext(None), (None, None, None))


class TestApiBackfill(unittest.TestCase):
    """The backfill fills BOTH metadata (from summary) and counts (from content)
    per revision, fetched via pywikibot's api.PropertyGenerator (server-side
    rvuser + content) and recorded through the resolved path. Mocked end to end
    (generator + registry) — no replica, no network. Continuation/throttle/
    maxlag are pywikibot's responsibility, not re-tested here."""

    def _registry(self, dashboards=None):
        registry = MagicMock()
        registry.list_dashboards_for_backfill.return_value = (
            dashboards if dashboards is not None else [("Wikidata:X", 3, 7)]
        )
        registry.record_resolved_backfilled_run.return_value = True
        return registry

    def _page(self, revs):
        """A generator page dict (formatversion 1: content under slot '*').
        ``revs`` is a list of (revid, timestamp, comment, content)."""
        return {
            "revisions": [
                {
                    "revid": revid,
                    "timestamp": ts,
                    "comment": comment,
                    "slots": {"main": {"*": content}},
                }
                for (revid, ts, comment, content) in revs
            ]
        }

    def _patch_generator(self, pages_by_call):
        """Patch api.PropertyGenerator so each call yields the given pages.

        ``pages_by_call`` is a list (one entry per dashboard) of lists of page
        dicts; a page-dict entry that is an Exception is raised instead.
        """
        calls = iter(pages_by_call)

        def factory(prop, site=None, parameters=None):
            pages = next(calls)
            factory.last_parameters = parameters

            def gen():
                for p in pages:
                    if isinstance(p, Exception):
                        raise p
                    yield p

            return gen()

        factory.last_parameters = None
        return patch(
            "pywikibot.data.api.PropertyGenerator", side_effect=factory
        ), factory

    def _run(self, registry, pages_by_call, limit=None):
        patcher, factory = self._patch_generator(pages_by_call)
        with patcher:
            inserted = ApiRunsBackfiller(
                MagicMock(hostname=lambda: "www.wikidata.org"), registry=registry
            ).backfill_runs(limit=limit)
        return inserted, factory

    def test_fills_metadata_and_counts_in_one_pass(self):
        registry = self._registry([("Wikidata:X", 3, 7)])
        pages = [
            self._page(
                [
                    (
                        999,
                        "2026-02-13T01:18:34Z",
                        "Weekly update of property usage stats using QLever (16s)",
                        _CURRENT_TABLE,
                    )
                ]
            )
        ]
        inserted, _ = self._run(registry, [pages])

        self.assertEqual(inserted, 1)
        dashboard_id, wiki_id, run, finished_at = (
            registry.record_resolved_backfilled_run.call_args[0]
        )
        self.assertEqual((dashboard_id, wiki_id), (3, 7))
        self.assertEqual(run.trigger_source, "CRON")
        self.assertEqual(run.sparql_engine, "QLever")
        self.assertEqual(run.duration_ms, 16000)
        self.assertEqual(run.entity_total, 39163)
        self.assertEqual(run.column_count, 2)
        self.assertEqual(finished_at, "2026-02-13 01:18:34")
        registry.conn.commit.assert_called()

    def test_refetches_truncated_revision_content(self):
        """A revision whose batched content is truncated (non-empty but no
        totals row → all-None shape) is re-fetched alone by revid, and the full
        content then yields real counts."""
        registry = self._registry([("Wikidata:X", 3, 7)])
        truncated = '{| class="wikitable sortable"\n| some cut-off content\n'
        first_pass = [
            self._page([(999, "2026-02-13T01:18:34Z", "Weekly update", truncated)])
        ]
        # The re-fetch (revids=999) returns the complete table.
        refetch = [self._page([(999, "2026-02-13T01:18:34Z", "", _CURRENT_TABLE)])]
        inserted, factory = self._run(registry, [first_pass, refetch])

        self.assertEqual(inserted, 1)
        run = registry.record_resolved_backfilled_run.call_args[0][2]
        self.assertEqual(run.entity_total, 39163)  # recovered from re-fetch
        self.assertEqual(run.column_count, 2)
        # The re-fetch call was by revids for the single revision.
        self.assertEqual(factory.last_parameters["revids"], 999)

    def test_unrecoverable_revision_records_null_counts(self):
        """If even the re-fetch won't parse, the run is still recorded with NULL
        counts (acceptable) rather than dropped."""
        registry = self._registry([("Wikidata:X", 3, 7)])
        garbage = '{| class="wikitable"\n| still no totals row\n'
        first_pass = [
            self._page([(999, "2026-02-13T01:18:34Z", "Weekly update", garbage)])
        ]
        refetch = [self._page([(999, "2026-02-13T01:18:34Z", "", garbage)])]
        inserted, _ = self._run(registry, [first_pass, refetch])

        self.assertEqual(inserted, 1)
        run = registry.record_resolved_backfilled_run.call_args[0][2]
        self.assertIsNone(run.entity_total)
        self.assertIsNone(run.grouping_count)
        self.assertIsNone(run.column_count)

    def test_query_filters_to_bot_with_content(self):
        """The generator is parameterised with the bot filter and content pull."""
        registry = self._registry([("Wikidata:X", 3, 7)])
        _, factory = self._run(registry, [[self._page([])]])

        params = factory.last_parameters
        self.assertEqual(params["rvuser"], "InteGraalityBot")
        self.assertIn("content", params["rvprop"])
        self.assertEqual(params["rvlimit"], REV_BATCH)
        self.assertEqual(params["titles"], "Wikidata:X")

    def test_error_on_one_dashboard_is_isolated(self):
        """A dashboard whose fetch raises is logged and skipped; the batch
        continues and records the good one."""
        registry = self._registry([("Bad", 3, 7), ("Good", 4, 7)])
        pages_by_call = [
            [RuntimeError("boom")],  # Bad: generator raises
            [
                self._page(
                    [(2, "2026-02-13T01:18:34Z", "Weekly update", _CURRENT_TABLE)]
                )
            ],
        ]
        inserted, _ = self._run(registry, pages_by_call)
        self.assertEqual(inserted, 1)

    def test_no_dashboards_is_a_noop(self):
        registry = self._registry([])
        inserted, factory = self._run(registry, [])
        self.assertEqual(inserted, 0)
        self.assertIsNone(factory.last_parameters)  # generator never built

    def test_limit_caps_dashboards(self):
        registry = self._registry([("A", 1, 7), ("B", 2, 7), ("C", 3, 7)])
        # Only two dashboards should be queried under limit=2.
        inserted, _ = self._run(registry, [[self._page([])], [self._page([])]], limit=2)
        self.assertEqual(inserted, 0)  # empty pages, but no crash on the 3rd


class TestTimestampConversion(unittest.TestCase):
    def test_iso_z_to_naive_datetime(self):
        self.assertEqual(
            ApiRunsBackfiller._timestamp_to_datetime_str("2026-02-13T01:18:34Z"),
            "2026-02-13 01:18:34",
        )

    def test_malformed_timestamp_raises(self):
        with self.assertRaises(ValueError):
            ApiRunsBackfiller._timestamp_to_datetime_str("not-a-timestamp")


class TestMain(unittest.TestCase):
    @patch("integraality.runs_backfiller.pywikibot.Site")
    @patch("integraality.runs_backfiller.ApiRunsBackfiller")
    @patch("sys.argv", ["prog", "https://commons.wikimedia.org/wiki/", "--limit", "5"])
    def test_main_builds_site_and_runs(self, mock_cls, mock_site):
        from integraality.runs_backfiller import main

        main()
        mock_site.assert_called_once_with(url="https://commons.wikimedia.org/wiki/")
        mock_cls.assert_called_once_with(mock_site.return_value)
        mock_cls.return_value.backfill_runs.assert_called_once_with(limit=5)

    @patch("integraality.runs_backfiller.pywikibot.Site")
    @patch("integraality.runs_backfiller.ApiRunsBackfiller")
    @patch("sys.argv", ["prog"])
    def test_main_defaults_to_wikidata(self, mock_cls, mock_site):
        from integraality.runs_backfiller import main

        main()
        mock_site.assert_called_once_with(url="https://www.wikidata.org/wiki/")
        mock_cls.return_value.backfill_runs.assert_called_once_with(limit=None)


if __name__ == "__main__":
    unittest.main()
