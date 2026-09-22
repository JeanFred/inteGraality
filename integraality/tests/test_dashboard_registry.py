"""Tests for dashboard_registry module."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from ..dashboard_registry import (
    RECENT_RUNS_STRIP_SIZE,
    DashboardRegistry,
    RunResult,
)


def _dt(ts):
    """Build a naive datetime from 'YYYY-MM-DD HH:MM:SS' − mirrors what the DB
    driver returns for finished_at, so tests exercise the production path."""
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")


class TestDashboardRegistry(unittest.TestCase):
    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=self.mock_cursor
        )
        self.mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        # A real cursor always exposes an int rowcount; default it so INSERT
        # helpers that read it (_insert_run) don't see a bare MagicMock.
        self.mock_cursor.rowcount = 1
        self.registry = DashboardRegistry(conn=self.mock_conn)

    def test_record(self):
        # Empty wikis preload → wiki miss → INSERT (id 7). Page miss (fetchone
        # None) → page INSERT (id 20). Dashboard miss (fetchone None) → INSERT.
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = None
        self.mock_cursor.lastrowid = 7

        self.registry.record(
            site_hostname="www.wikidata.org",
            page_id=12345,
            page_url="https://www.wikidata.org/wiki/Wikidata%3ATest",
            page_title="Wikidata:Test",
            site_name="Wikidata",
            namespace_canonical="Project",
            namespace_localized="Wikidata",
            root_page="Test",
        )

        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        # wiki preload, wiki INSERT, page SELECT, page INSERT, dashboard SELECT,
        # dashboard INSERT.
        self.assertIn("SELECT id, hostname, name FROM wikis", executed[0])
        self.assertTrue(any("INSERT INTO wikis" in s for s in executed))
        self.assertTrue(any("SELECT id FROM pages" in s for s in executed))
        self.assertTrue(any("INSERT INTO pages" in s for s in executed))
        self.assertTrue(any("SELECT id FROM dashboards" in s for s in executed))
        self.assertTrue(any("INSERT INTO dashboards (page_pk)" in s for s in executed))
        # The page INSERT carries the wiki id and all page metadata.
        page_insert = next(
            c[0]
            for c in self.mock_cursor.execute.call_args_list
            if "INSERT INTO pages" in c[0][0]
        )
        self.assertEqual(
            page_insert[1],
            (
                7,
                12345,
                "https://www.wikidata.org/wiki/Wikidata%3ATest",
                "Wikidata:Test",
                "Project",
                "Wikidata",
                "Test",
            ),
        )
        self.mock_conn.commit.assert_called_once()

    def test_record_existing_page_updates_not_inserts(self):
        """An existing page is UPDATEd in place (no id burn), and an existing
        dashboard is not re-inserted."""
        self.mock_cursor.fetchall.return_value = [
            {"id": 7, "hostname": "www.wikidata.org", "name": "Wikidata"},
        ]
        # page SELECT finds id 20; dashboards SELECT finds an existing row.
        self.mock_cursor.fetchone.side_effect = [{"id": 20}, {"id": 3}]

        self.registry.record(
            site_hostname="www.wikidata.org",
            page_id=12345,
            page_url="https://www.wikidata.org/wiki/New_Title",
            page_title="New Title",
            site_name="Wikidata",
            namespace_canonical="Project",
            namespace_localized="Wikidata",
            root_page="New Title",
        )

        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        # Existing page → UPDATE, no page INSERT. Existing dashboard → no INSERT.
        self.assertTrue(any("UPDATE pages" in s for s in executed))
        self.assertEqual(sum("INSERT INTO pages" in s for s in executed), 0)
        self.assertEqual(sum("INSERT INTO dashboards" in s for s in executed), 0)
        # The UPDATE refreshes mutable display columns for the found page id.
        page_update = next(
            c[0]
            for c in self.mock_cursor.execute.call_args_list
            if "UPDATE pages" in c[0][0]
        )
        self.assertEqual(page_update[1][-1], 20)  # WHERE id = 20

    def _record(self, hostname, page_id, site_name):
        self.registry.record(
            site_hostname=hostname,
            page_id=page_id,
            page_url=f"https://{hostname}/wiki/P{page_id}",
            page_title=f"P{page_id}",
            site_name=site_name,
            namespace_canonical="Project",
            namespace_localized=site_name,
            root_page=f"P{page_id}",
        )

    def test_wiki_preloaded_once_then_cached(self):
        """The wikis table is preloaded once; later records touch no wiki SQL."""
        self.mock_cursor.fetchall.return_value = [
            {"id": 7, "hostname": "www.wikidata.org", "name": "Wikidata"},
        ]
        # Every page/dashboard existence check misses → INSERT paths.
        self.mock_cursor.fetchone.return_value = None

        self._record("www.wikidata.org", 1, "Wikidata")
        self._record("www.wikidata.org", 2, "Wikidata")
        self._record("www.wikidata.org", 3, "Wikidata")

        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        self.assertEqual(
            sum("SELECT id, hostname, name FROM wikis" in sql for sql in executed), 1
        )
        self.assertEqual(sum("INSERT INTO wikis" in sql for sql in executed), 0)
        self.assertEqual(sum("UPDATE wikis" in sql for sql in executed), 0)
        # Each record inserts a page and a dashboard row.
        self.assertEqual(sum("INSERT INTO pages" in sql for sql in executed), 3)
        self.assertEqual(
            sum("INSERT INTO dashboards (page_pk)" in sql for sql in executed), 3
        )
        self.assertEqual(self.mock_conn.commit.call_count, 3)

    def test_new_wiki_inserted_once_on_miss(self):
        """A hostname not in the preloaded set triggers exactly one INSERT."""
        self.mock_cursor.fetchall.return_value = []  # empty table
        self.mock_cursor.lastrowid = 9

        self._record("meta.wikimedia.org", 1, "Meta-Wiki")
        self._record("meta.wikimedia.org", 2, "Meta-Wiki")

        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        # One preload, one INSERT (first miss), none on the cached second call.
        self.assertEqual(
            sum("SELECT id, hostname, name FROM wikis" in sql for sql in executed), 1
        )
        self.assertEqual(sum("INSERT INTO wikis" in sql for sql in executed), 1)

    def test_name_self_heal_on_change(self):
        """A changed display name is refreshed with an UPDATE (no INSERT), and
        the in-memory cache is updated so a second record does not UPDATE again.
        """
        self.mock_cursor.fetchall.return_value = [
            {"id": 7, "hostname": "www.wikidata.org", "name": "Old Name"},
        ]

        self._record("www.wikidata.org", 1, "Wikidata")

        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        self.assertEqual(sum("UPDATE wikis SET name" in sql for sql in executed), 1)
        self.assertEqual(sum("INSERT INTO wikis" in sql for sql in executed), 0)

        # Second record with the now-healed name: cache holds the new name, so
        # no further UPDATE should fire (this is the point of updating the cache).
        self._record("www.wikidata.org", 2, "Wikidata")
        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        self.assertEqual(sum("UPDATE wikis SET name" in sql for sql in executed), 1)

    def test_name_unchanged_issues_no_wiki_write(self):
        """An unchanged display name issues no wiki write."""
        self.mock_cursor.fetchall.return_value = [
            {"id": 7, "hostname": "www.wikidata.org", "name": "Wikidata"},
        ]

        self._record("www.wikidata.org", 1, "Wikidata")

        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        self.assertEqual(sum("UPDATE wikis" in sql for sql in executed), 0)
        self.assertEqual(sum("INSERT INTO wikis" in sql for sql in executed), 0)

    def test_list_dashboards(self):
        self.mock_cursor.fetchall.return_value = [
            {
                "page_url": "https://www.wikidata.org/wiki/Page1",
                "page_title": "Page1",
                "site_hostname": "www.wikidata.org",
                "site_name": "Wikidata",
            },
            {
                "page_url": "https://www.wikidata.org/wiki/Page2",
                "page_title": "Page2",
                "site_hostname": "www.wikidata.org",
                "site_name": "Wikidata",
            },
        ]

        results = self.registry.list_dashboards()

        executed_sql = self.mock_cursor.execute.call_args[0][0]
        # The query joins wikis and aliases its columns back to
        # site_hostname/site_name — the contract that keeps templates working.
        self.assertIn("JOIN wikis", executed_sql)
        self.assertIn("w.hostname AS site_hostname", executed_sql)
        self.assertIn("w.name AS site_name", executed_sql)
        # No filters passed → no filter conditions on the outer query. (The
        # last_success_at subquery has its own WHERE status = 'OK', so assert
        # the absence of a filter predicate rather than the WHERE keyword.)
        self.assertNotIn("w.hostname = %s", executed_sql)
        self.assertNotIn("p.namespace_canonical = %s", executed_sql)
        self.assertNotIn("r.status = %s", executed_sql)
        self.assertEqual(len(results), 2)

    def test_list_dashboards_carries_latest_run(self):
        """Each row LEFT-joins its latest run (MAX(finished_at) per dashboard),
        so /browse can badge status without an N+1 per-dashboard read."""
        self.mock_cursor.fetchall.return_value = [
            {
                "page_title": "Page1",
                "latest_status": "OK",
                "latest_finished_at": "2026-09-11 10:00:00",
                "latest_duration_ms": 72000,
                "last_success_at": "2026-09-11 10:00:00",
                "recent_statuses": "OK,FAIL",
                "failures_since_success": 1,
            },
        ]

        results = self.registry.list_dashboards()

        # The health fields are surfaced on the row (behavior, not SQL text).
        row = results[0]
        for field in (
            "latest_status",
            "last_success_at",
            "recent_statuses",
            "failures_since_success",
        ):
            self.assertIn(field, row)

        sql = self.mock_cursor.execute.call_args[0][0]
        # Semantic properties (not cosmetic formatting):
        # - the latest/last-OK picks are backfill-safe: ordered by finished_at
        #   with an id tiebreak, so out-of-id-order history still ranks right.
        self.assertIn("finished_at DESC, id DESC", sql)
        # - failures_since_success compares the (finished_at, id) tuple, so a
        #   FAIL sharing the last-OK's whole second is still counted; a bare
        #   finished_at > would drop it (the reviewer's tie bug).
        self.assertIn("(f.finished_at, f.id) > (ok.finished_at, ok.id)", sql)
        # - the strip's LIMIT binds first (FROM-clause), ahead of any filter.
        params = self.mock_cursor.execute.call_args[0][1]
        self.assertEqual(params[0], RECENT_RUNS_STRIP_SIZE)
        self.assertEqual(row["latest_status"], "OK")

    def test_list_dashboards_filtered_by_status(self):
        """status filters on the latest run's status (r.status)."""
        self.mock_cursor.fetchall.return_value = []
        self.registry.list_dashboards(status="FAIL")
        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("r.status = %s", sql)
        self.assertEqual(params, (RECENT_RUNS_STRIP_SIZE, "FAIL"))

    def test_list_dashboards_does_not_preload_wiki_cache(self):
        """Read-only use must not trigger the wiki preload SELECT."""
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards()

        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        self.assertEqual(
            sum("SELECT id, hostname, name FROM wikis" in sql for sql in executed), 0
        )

    def test_list_dashboards_filtered(self):
        self.mock_cursor.fetchall.return_value = [
            {
                "page_url": "https://meta.wikimedia.org/wiki/Test",
                "page_title": "Test",
                "site_hostname": "meta.wikimedia.org",
                "site_name": "Meta-Wiki",
            },
        ]

        results = self.registry.list_dashboards(site_hostname="meta.wikimedia.org")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("WHERE w.hostname = %s", sql)
        self.assertEqual(params, (RECENT_RUNS_STRIP_SIZE, "meta.wikimedia.org"))
        self.assertEqual(len(results), 1)

    def test_list_wikis(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_wikis()

        sql = self.mock_cursor.execute.call_args[0][0]
        # The method's real work is counting dashboards per wiki.
        self.assertIn("JOIN dashboards", sql)
        self.assertIn("COUNT(d.id)", sql)
        self.assertIn("GROUP BY", sql)
        self.assertIn("ORDER BY count DESC", sql)
        # No namespace filter passed → no WHERE clause.
        self.assertNotIn("WHERE", sql)

    def test_list_namespaces(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_namespaces()

        sql = self.mock_cursor.execute.call_args[0][0]
        self.assertIn("COUNT(*)", sql)
        self.assertIn("GROUP BY p.namespace_canonical", sql)
        self.assertIn("ORDER BY count DESC", sql)
        # No wiki filter passed → no WHERE clause.
        self.assertNotIn("WHERE", sql)

    def test_list_dashboards_filtered_by_namespace(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(namespace_canonical="User")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("p.namespace_canonical = %s", sql)
        self.assertEqual(params, (RECENT_RUNS_STRIP_SIZE, "User"))

    def test_list_dashboards_filtered_by_main_namespace(self):
        """Passing "" filters to the Main namespace (empty canonical name).

        This pins the `is not None` contract: a regression to a truthiness
        check (`if namespace_canonical:`) would silently drop this filter.
        """
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(namespace_canonical="")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("p.namespace_canonical = %s", sql)
        self.assertEqual(params, (RECENT_RUNS_STRIP_SIZE, ""))

    def test_list_dashboards_no_namespace_filter_when_none(self):
        """namespace_canonical=None applies no namespace filter."""
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(namespace_canonical=None)

        sql = self.mock_cursor.execute.call_args[0][0]
        self.assertNotIn("p.namespace_canonical = %s", sql)

    def test_list_wikis_filtered_by_namespace(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_wikis(namespace_canonical="User")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("p.namespace_canonical = %s", sql)
        self.assertEqual(params, ("User",))

    def test_list_wikis_filtered_by_main_namespace(self):
        """list_wikis also honours "" as the Main namespace (is not None)."""
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_wikis(namespace_canonical="")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("p.namespace_canonical = %s", sql)
        self.assertEqual(params, ("",))

    def test_list_namespaces_filtered_by_wiki(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_namespaces(site_hostname="meta.wikimedia.org")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("w.hostname = %s", sql)
        self.assertEqual(params, ("meta.wikimedia.org",))

    def test_list_roots_filtered(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_roots(
            site_hostname="www.wikidata.org", namespace_canonical="Project"
        )

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("w.hostname = %s", sql)
        self.assertIn("p.namespace_canonical = %s", sql)
        self.assertEqual(params, ("www.wikidata.org", "Project"))

    def test_list_dashboards_filtered_by_root(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(root_page="WikiProject Music")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("p.root_page = %s", sql)
        self.assertEqual(params, (RECENT_RUNS_STRIP_SIZE, "WikiProject Music"))

    def test_list_dashboards_search_uses_like(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(search="coverage")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn(r"p.page_title LIKE %s ESCAPE '\'", sql)
        self.assertEqual(params, (RECENT_RUNS_STRIP_SIZE, "%coverage%"))

    def test_list_dashboards_search_escapes_wildcards(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(search="100%_done")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn(r"ESCAPE '\'", sql)
        self.assertEqual(params, (RECENT_RUNS_STRIP_SIZE, r"%100\%\_done%"))

    def test_list_dashboards_combined_filters(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(
            site_hostname="www.wikidata.org",
            namespace_canonical="Project",
            root_page="WikiProject Music",
            search="album",
        )

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("w.hostname = %s", sql)
        self.assertIn("p.namespace_canonical = %s", sql)
        self.assertIn("p.root_page = %s", sql)
        self.assertIn("p.page_title LIKE %s", sql)
        self.assertEqual(
            params,
            (
                RECENT_RUNS_STRIP_SIZE,
                "www.wikidata.org",
                "Project",
                "WikiProject Music",
                "%album%",
            ),
        )

    def test_list_roots(self):
        self.mock_cursor.fetchall.return_value = [
            {"root_page": "Jean-Fred"},
            {"root_page": "WikiProject Music"},
        ]

        results = self.registry.list_roots()

        sql = self.mock_cursor.execute.call_args[0][0]
        self.assertIn("SELECT DISTINCT p.root_page", sql)
        self.assertEqual(results, ["Jean-Fred", "WikiProject Music"])

    def test_list_dashboards_missing_page_metadata(self):
        """Filters on page_created_at IS NULL (the reliably-present field),
        not page_creator (which can be suppressed), and always scopes to the
        given wiki. Returns pages.id as id."""
        self.mock_cursor.fetchall.return_value = [
            {"id": 1, "page_title": "Foo", "site_hostname": "www.wikidata.org"},
        ]

        results = self.registry.list_dashboards_missing_page_metadata(
            site_hostname="www.wikidata.org"
        )

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("p.page_created_at IS NULL", sql)
        self.assertNotIn("page_creator IS NULL", sql)
        self.assertIn("w.hostname = %s", sql)
        self.assertEqual(params, ("www.wikidata.org",))
        self.assertEqual(len(results), 1)

    def test_list_dashboards_missing_page_metadata_filtered_by_wiki(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards_missing_page_metadata(
            site_hostname="meta.wikimedia.org"
        )

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("p.page_created_at IS NULL", sql)
        self.assertIn("w.hostname = %s", sql)
        self.assertEqual(params, ("meta.wikimedia.org",))

    def test_update_page_metadata(self):
        self.registry.update_page_metadata(
            page_pk=42,
            page_creator="Alice",
            page_created_at="2020-01-02T03:04:05Z",
        )

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("UPDATE pages", sql)
        self.assertIn("page_creator = %s", sql)
        self.assertIn("page_created_at = %s", sql)
        self.assertIn("WHERE id = %s", sql)
        self.assertEqual(params, ("Alice", "2020-01-02T03:04:05Z", 42))
        self.mock_conn.commit.assert_called_once()

    def _page_metadata(self):
        return {
            "site_hostname": "www.wikidata.org",
            "site_name": "Wikidata",
            "page_id": 12345,
            "page_url": "https://www.wikidata.org/wiki/Wikidata:Test",
            "page_title": "Wikidata:Test",
            "namespace_canonical": "Project",
            "namespace_localized": "Wikidata",
            "root_page": "Test",
        }

    def _run_insert_by_column(self):
        """Map the dashboard_runs INSERT's columns to their bound values, so
        assertions read by name and survive column reordering."""
        sql, params = next(
            c[0]
            for c in self.mock_cursor.execute.call_args_list
            if "INTO dashboard_runs" in c[0][0]
        )
        cols = sql.split("(", 1)[1].split(")", 1)[0]
        names = [c.strip() for c in cols.replace("\n", " ").split(",")]
        return dict(zip(names, params))

    def test_record_run_inserts_a_run_row(self):
        """record_run resolves wiki/page/dashboard then appends one run row."""
        self.mock_cursor.fetchall.return_value = [
            {"id": 7, "hostname": "www.wikidata.org", "name": "Wikidata"},
        ]
        # page SELECT -> id 20, dashboard SELECT -> id 3.
        self.mock_cursor.fetchone.side_effect = [{"id": 20}, {"id": 3}]

        self.registry.record_run(
            self._page_metadata(),
            RunResult.ok(
                trigger_source="CRON",
                duration_ms=72000,
                sparql_engine="Wikidata Query Service",
                revision_id=555,
                entity_total=39163,
                grouping_count=40,
                column_count=7,
            ),
        )

        row = self._run_insert_by_column()
        # Resolved ids, plus the OK-specific fields.
        self.assertEqual(row["dashboard_id"], 3)
        self.assertEqual(row["wiki_id"], 7)
        self.assertEqual(row["status"], "OK")
        self.assertEqual(row["revision_id"], 555)
        self.assertEqual(row["entity_total"], 39163)
        self.mock_conn.commit.assert_called_once()

    def test_record_run_fail_carries_category_not_revision(self):
        self.mock_cursor.fetchall.return_value = [
            {"id": 7, "hostname": "www.wikidata.org", "name": "Wikidata"},
        ]
        self.mock_cursor.fetchone.side_effect = [{"id": 20}, {"id": 3}]

        self.registry.record_run(
            self._page_metadata(),
            RunResult.fail(
                trigger_source="WEB",
                duration_ms=200,
                error_category="query",
                error_detail="SPARQL timeout",
            ),
        )

        row = self._run_insert_by_column()
        self.assertEqual(row["status"], "FAIL")
        self.assertEqual(row["error_category"], "query")
        self.assertIsNone(row["revision_id"])  # NULL on failure

    def test_list_dashboards_for_backfill_returns_title_and_ids(self):
        """Returns (page_title, dashboard_id, wiki_id) rows for the API
        backfiller: title to query the API, ids for the resolved insert."""
        self.mock_cursor.fetchall.return_value = [
            {"page_title": "Wikidata:A", "dashboard_id": 3, "wiki_id": 7},
            {"page_title": "Wikidata:B", "dashboard_id": 4, "wiki_id": 7},
        ]

        result = self.registry.list_dashboards_for_backfill("www.wikidata.org")

        self.assertEqual(result, [("Wikidata:A", 3, 7), ("Wikidata:B", 4, 7)])
        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("p.page_title", sql)
        self.assertIn("w.hostname = %s", sql)
        self.assertEqual(params, ("www.wikidata.org",))

    def test_list_dashboards_for_backfill_only_missing_excludes_recorded(self):
        """only_missing adds a NOT EXISTS on dashboard_runs so already-recorded
        dashboards are skipped; params are unchanged."""
        self.mock_cursor.fetchall.return_value = [
            {"page_title": "Wikidata:A", "dashboard_id": 3, "wiki_id": 7},
        ]

        result = self.registry.list_dashboards_for_backfill(
            "www.wikidata.org", only_missing=True
        )

        self.assertEqual(result, [("Wikidata:A", 3, 7)])
        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("dashboard_runs", sql)
        self.assertEqual(params, ("www.wikidata.org",))

    def test_record_resolved_backfilled_run_inserts_ignore_no_commit(self):
        """Inserts against resolved ids via INSERT IGNORE; does NOT commit
        (the backfiller commits per dashboard)."""
        self.mock_cursor.rowcount = 1

        inserted = self.registry.record_resolved_backfilled_run(
            3,
            7,
            RunResult.ok(
                trigger_source="CRON",
                duration_ms=102000,
                sparql_engine="QLever",
                revision_id=999,
                entity_total=None,
                grouping_count=None,
                column_count=None,
            ),
            "2021-03-04 05:06:07",
        )

        self.assertTrue(inserted)
        sql, _ = next(
            c[0]
            for c in self.mock_cursor.execute.call_args_list
            if "INTO dashboard_runs" in c[0][0]
        )
        self.assertIn("INSERT IGNORE INTO dashboard_runs", sql)
        row = self._run_insert_by_column()
        self.assertEqual(row["dashboard_id"], 3)
        self.assertEqual(row["wiki_id"], 7)
        self.assertEqual(row["finished_at"], "2021-03-04 05:06:07")
        self.assertEqual(row["revision_id"], 999)
        self.mock_conn.commit.assert_not_called()

    def test_record_resolved_backfilled_run_returns_false_on_duplicate(self):
        self.mock_cursor.rowcount = 0  # INSERT IGNORE skipped the duplicate
        inserted = self.registry.record_resolved_backfilled_run(
            3,
            7,
            RunResult.ok(
                trigger_source="CRON",
                duration_ms=None,
                sparql_engine="QLever",
                revision_id=999,
                entity_total=None,
                grouping_count=None,
                column_count=None,
            ),
            "2021-03-04 05:06:07",
        )
        self.assertFalse(inserted)

    def test_record_resolved_backfilled_run_requires_revision_id(self):
        with self.assertRaises(ValueError):
            self.registry.record_resolved_backfilled_run(
                3,
                7,
                RunResult.ok(
                    trigger_source="CRON",
                    duration_ms=None,
                    sparql_engine="QLever",
                    revision_id=None,
                    entity_total=None,
                    grouping_count=None,
                    column_count=None,
                ),
                "2021-03-04 05:06:07",
            )

    def test_list_runs_orders_newest_first_and_limits(self):
        self.mock_cursor.fetchall.return_value = [
            {"page_title": "A", "status": "OK"},
            {"page_title": "B", "status": "FAIL"},
        ]

        result = self.registry.list_runs()

        self.assertEqual(len(result), 2)
        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("FROM dashboard_runs", sql)
        self.assertIn("ORDER BY r.finished_at DESC", sql)
        self.assertIn("LIMIT %s", sql)
        self.assertEqual(params, (100,))  # default limit

    def test_list_runs_scoped_to_wiki(self):
        self.mock_cursor.fetchall.return_value = []
        self.registry.list_runs(site_hostname="commons.wikimedia.org")
        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("w.hostname = %s", sql)
        self.assertEqual(params, ("commons.wikimedia.org", 100))

    def test_get_dashboard_returns_identity_row(self):
        """Keyed on (hostname, page_title); returns the aliased identity row."""
        self.mock_cursor.fetchone.return_value = {
            "page_url": "https://www.wikidata.org/wiki/X",
            "page_title": "X",
            "site_hostname": "www.wikidata.org",
            "site_name": "Wikidata",
        }

        row = self.registry.get_dashboard("www.wikidata.org", "X")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("WHERE w.hostname = %s AND p.page_title = %s", sql)
        self.assertIn("w.hostname AS site_hostname", sql)
        self.assertEqual(params, ("www.wikidata.org", "X"))
        self.assertEqual(row["page_title"], "X")

    def test_get_dashboard_unknown_returns_none(self):
        self.mock_cursor.fetchone.return_value = None
        self.assertIsNone(self.registry.get_dashboard("www.wikidata.org", "Nope"))

    def test_get_dashboard_does_not_preload_wiki_cache(self):
        """Read-only use must not trigger the wiki preload SELECT."""
        self.mock_cursor.fetchone.return_value = None
        self.registry.get_dashboard("www.wikidata.org", "X")
        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        self.assertEqual(
            sum("SELECT id, hostname, name FROM wikis" in sql for sql in executed), 0
        )

    def test_list_dashboard_run_history_orders_oldest_first(self):
        """Unlimited history is scanned in ascending (finished_at, id) order so
        a chart reads left-to-right; keyed on (hostname, page_title)."""
        self.mock_cursor.fetchall.return_value = [
            {"finished_at": "2019-05-22 20:28:56", "status": "OK"},
            {"finished_at": "2019-05-22 20:34:24", "status": "OK"},
        ]

        result = self.registry.list_dashboard_run_history("www.wikidata.org", "X")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("WHERE w.hostname = %s AND p.page_title = %s", sql)
        self.assertIn("ORDER BY r.finished_at ASC, r.id ASC", sql)
        self.assertNotIn("LIMIT", sql)
        self.assertEqual(params, ("www.wikidata.org", "X"))
        self.assertEqual(len(result), 2)

    def test_list_dashboard_run_history_limit_keeps_newest_then_resorts(self):
        """With a limit, keep the newest N (DESC subquery + LIMIT) but return
        them oldest->newest for display."""
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboard_run_history("www.wikidata.org", "X", limit=50)

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("ORDER BY r.finished_at DESC, r.id DESC", sql)
        self.assertIn("LIMIT %s", sql)
        self.assertIn("ORDER BY finished_at ASC", sql)
        self.assertEqual(params, ("www.wikidata.org", "X", 50))

    def test_list_dashboard_run_history_does_not_preload_wiki_cache(self):
        self.mock_cursor.fetchall.return_value = []
        self.registry.list_dashboard_run_history("www.wikidata.org", "X")
        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        self.assertEqual(
            sum("SELECT id, hostname, name FROM wikis" in sql for sql in executed), 0
        )

    def test_compute_health_summarizes_runs(self):
        """compute_health is a pure summary over an oldest->newest run list:
        counts, success rate, first/last, last success, trailing failure streak,
        and an error-category breakdown."""
        runs = [
            {
                "finished_at": _dt("2019-01-01 00:00:00"),
                "status": "OK",
                "error_category": None,
            },
            {
                "finished_at": _dt("2019-01-02 00:00:00"),
                "status": "OK",
                "error_category": None,
            },
            {
                "finished_at": _dt("2019-01-03 00:00:00"),
                "status": "FAIL",
                "error_category": "timeout",
            },
            {
                "finished_at": _dt("2019-01-04 00:00:00"),
                "status": "FAIL",
                "error_category": "query",
            },
        ]

        health = DashboardRegistry.compute_health(runs)

        self.assertEqual(health["total"], 4)
        self.assertEqual(health["ok"], 2)
        self.assertEqual(health["fail"], 2)
        self.assertEqual(health["success_rate"], 0.5)
        self.assertEqual(health["first_run_at"], _dt("2019-01-01 00:00:00"))
        self.assertEqual(health["last_run_at"], _dt("2019-01-04 00:00:00"))
        # Last OK is the 2nd run; the two trailing FAILs form the streak.
        self.assertEqual(health["last_success_at"], _dt("2019-01-02 00:00:00"))
        self.assertEqual(health["failure_streak"], 2)
        self.assertEqual(health["error_categories"], {"timeout": 1, "query": 1})

    def test_compute_health_all_ok_has_no_streak(self):
        runs = [
            {
                "finished_at": _dt("2019-01-01 00:00:00"),
                "status": "OK",
                "error_category": None,
            },
            {
                "finished_at": _dt("2019-01-02 00:00:00"),
                "status": "OK",
                "error_category": None,
            },
        ]
        health = DashboardRegistry.compute_health(runs)
        self.assertEqual(health["failure_streak"], 0)
        self.assertEqual(health["success_rate"], 1.0)
        self.assertEqual(health["error_categories"], {})

    def test_compute_health_empty(self):
        health = DashboardRegistry.compute_health([])
        self.assertEqual(health["total"], 0)
        self.assertIsNone(health["success_rate"])
        self.assertIsNone(health["last_success_at"])
        self.assertIsNone(health["first_run_at"])
        self.assertEqual(health["failure_streak"], 0)

    def test_compute_health_metric_deltas(self):
        """Each metric card gets current/first + both deltas, computed over the
        non-null observations (failed runs carry no counts)."""
        runs = [
            {
                "finished_at": _dt("2019-01-01 00:00:00"),
                "status": "OK",
                "error_category": None,
                "entity_total": 100,
                "grouping_count": 2,
                "column_count": 9,
            },
            {
                "finished_at": _dt("2019-02-01 00:00:00"),
                "status": "OK",
                "error_category": None,
                "entity_total": 150,
                "grouping_count": 5,
                "column_count": 9,
            },
            {
                "finished_at": _dt("2019-03-01 00:00:00"),
                "status": "OK",
                "error_category": None,
                "entity_total": 180,
                "grouping_count": 7,
                "column_count": 9,
            },
            # A failure carries no counts and must not affect the deltas.
            {
                "finished_at": _dt("2019-04-01 00:00:00"),
                "status": "FAIL",
                "error_category": "query",
                "entity_total": None,
                "grouping_count": None,
                "column_count": None,
            },
        ]

        m = DashboardRegistry.compute_health(runs)["metrics"]

        self.assertEqual(m["entity_total"]["current"], 180)
        self.assertEqual(m["entity_total"]["first"], 100)
        self.assertEqual(m["entity_total"]["delta_since_first"], 80)
        # Last change is 150 -> 180 (the FAIL's None is skipped).
        self.assertEqual(m["entity_total"]["delta_since_last"], 30)
        self.assertEqual(m["entity_total"]["series"], [100, 150, 180])
        # Columns never changed: deltas are zero, not None.
        self.assertEqual(m["column_count"]["delta_since_first"], 0)
        self.assertEqual(m["column_count"]["delta_since_last"], 0)

    def test_compute_health_metric_single_observation(self):
        """One observation: since-first delta is 0, since-last is None (no
        prior value to compare)."""
        runs = [
            {
                "finished_at": _dt("2019-01-01 00:00:00"),
                "status": "OK",
                "error_category": None,
                "entity_total": 100,
                "grouping_count": 2,
                "column_count": 9,
            },
        ]
        m = DashboardRegistry.compute_health(runs)["metrics"]
        self.assertEqual(m["entity_total"]["delta_since_first"], 0)
        self.assertIsNone(m["entity_total"]["delta_since_last"])

    def test_compute_health_metric_all_none(self):
        """All-failed history: a metric with no observations is all-None."""
        runs = [
            {
                "finished_at": _dt("2019-01-01 00:00:00"),
                "status": "FAIL",
                "error_category": "query",
                "entity_total": None,
                "grouping_count": None,
                "column_count": None,
            },
        ]
        m = DashboardRegistry.compute_health(runs)["metrics"]
        self.assertIsNone(m["entity_total"]["current"])
        self.assertIsNone(m["entity_total"]["delta_since_first"])
        self.assertEqual(m["entity_total"]["series"], [])

    def test_monthly_runs_buckets_ok_and_fail(self):
        """Runs are bucketed per calendar month into OK/FAIL counts."""
        runs = [
            {
                "finished_at": _dt("2019-01-05 00:00:00"),
                "status": "OK",
                "error_category": None,
            },
            {
                "finished_at": _dt("2019-01-20 00:00:00"),
                "status": "OK",
                "error_category": None,
            },
            {
                "finished_at": _dt("2019-01-28 00:00:00"),
                "status": "FAIL",
                "error_category": "query",
            },
        ]
        monthly = DashboardRegistry.compute_health(runs)["monthly_runs"]
        self.assertEqual(
            monthly,
            [{"month": "2019-01", "ok_cron": 2, "ok_web": 0, "ok": 2, "fail": 1}],
        )

    def test_monthly_runs_fills_empty_months(self):
        """Months between first and last run with no runs appear as zeros, so a
        bar chart's time axis stays continuous."""
        runs = [
            {
                "finished_at": _dt("2019-01-15 00:00:00"),
                "status": "OK",
                "error_category": None,
            },
            {
                "finished_at": _dt("2019-04-15 00:00:00"),
                "status": "OK",
                "error_category": None,
            },
        ]
        monthly = DashboardRegistry.compute_health(runs)["monthly_runs"]
        self.assertEqual(
            monthly,
            [
                {"month": "2019-01", "ok_cron": 1, "ok_web": 0, "ok": 1, "fail": 0},
                {"month": "2019-02", "ok_cron": 0, "ok_web": 0, "ok": 0, "fail": 0},
                {"month": "2019-03", "ok_cron": 0, "ok_web": 0, "ok": 0, "fail": 0},
                {"month": "2019-04", "ok_cron": 1, "ok_web": 0, "ok": 1, "fail": 0},
            ],
        )

    def test_monthly_runs_crosses_year_boundary(self):
        runs = [
            {
                "finished_at": _dt("2019-11-15 00:00:00"),
                "status": "OK",
                "error_category": None,
            },
            {
                "finished_at": _dt("2020-01-15 00:00:00"),
                "status": "FAIL",
                "error_category": "timeout",
            },
        ]
        months = [
            b["month"] for b in DashboardRegistry.compute_health(runs)["monthly_runs"]
        ]
        self.assertEqual(months, ["2019-11", "2019-12", "2020-01"])

    def test_monthly_runs_empty(self):
        self.assertEqual(DashboardRegistry.compute_health([])["monthly_runs"], [])

    def test_monthly_runs_splits_ok_by_trigger(self):
        """Successful runs split into cron vs web (manual); ok is their sum."""
        runs = [
            {
                "finished_at": _dt("2019-01-05 00:00:00"),
                "status": "OK",
                "trigger_source": "CRON",
                "error_category": None,
            },
            {
                "finished_at": _dt("2019-01-06 00:00:00"),
                "status": "OK",
                "trigger_source": "WEB",
                "error_category": None,
            },
            {
                "finished_at": _dt("2019-01-07 00:00:00"),
                "status": "OK",
                "trigger_source": "WEB",
                "error_category": None,
            },
        ]
        monthly = DashboardRegistry.compute_health(runs)["monthly_runs"]
        self.assertEqual(
            monthly,
            [{"month": "2019-01", "ok_cron": 1, "ok_web": 2, "ok": 3, "fail": 0}],
        )

    def test_engagement_web_vs_cron(self):
        """Engagement: web/cron counts, web share, and last manual (WEB) run."""
        runs = [
            {
                "finished_at": _dt("2019-01-05 00:00:00"),
                "status": "OK",
                "trigger_source": "CRON",
                "error_category": None,
            },
            {
                "finished_at": _dt("2019-02-10 00:00:00"),
                "status": "OK",
                "trigger_source": "WEB",
                "error_category": None,
            },
            {
                "finished_at": _dt("2019-03-15 00:00:00"),
                "status": "OK",
                "trigger_source": "CRON",
                "error_category": None,
            },
        ]
        e = DashboardRegistry.compute_health(runs)["engagement"]
        self.assertEqual(e["web"], 1)
        self.assertEqual(e["cron"], 2)
        self.assertAlmostEqual(e["web_share"], 1 / 3)
        self.assertEqual(e["last_web_at"], _dt("2019-02-10 00:00:00"))

    def test_engagement_no_web_runs(self):
        runs = [
            {
                "finished_at": _dt("2019-01-05 00:00:00"),
                "status": "OK",
                "trigger_source": "CRON",
                "error_category": None,
            },
        ]
        e = DashboardRegistry.compute_health(runs)["engagement"]
        self.assertEqual(e["web"], 0)
        self.assertIsNone(e["last_web_at"])
        self.assertEqual(e["web_share"], 0.0)

    def test_engagement_empty(self):
        e = DashboardRegistry.compute_health([])["engagement"]
        self.assertEqual(e["web"], 0)
        self.assertEqual(e["cron"], 0)
        self.assertIsNone(e["web_share"])
        self.assertIsNone(e["last_web_at"])

    def test_close(self):
        self.registry.close()
        self.mock_conn.close.assert_called_once()

    def test_close_is_idempotent(self):
        """Calling close() twice closes the connection once, then no-ops."""
        self.registry.close()
        self.registry.close()
        self.mock_conn.close.assert_called_once()

    def test_close_never_connected_is_noop(self):
        """close() on a registry whose connection was never created is a no-op."""
        registry = DashboardRegistry()  # no conn passed, conn never accessed
        registry.close()  # must not raise or create a connection

    def test_context_manager(self):
        with DashboardRegistry(conn=self.mock_conn):
            pass
        self.mock_conn.close.assert_called_once()


class TestDashboardRegistryLazyConnection(unittest.TestCase):
    @patch("integraality.dashboard_registry.get_connection")
    @patch("integraality.dashboard_registry.ensure_schema")
    def test_conn_created_lazily(self, mock_ensure, mock_get_conn):
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        registry = DashboardRegistry()
        mock_get_conn.assert_not_called()

        _ = registry.conn
        mock_get_conn.assert_called_once()
        mock_ensure.assert_called_once_with(mock_conn)


class RunResultTest(unittest.TestCase):
    """fail() requires an error_category, as an executable contract for the one
    DB invariant (chk_fail_has_category) — omitting it is a TypeError where you
    write it, not a DB CHECK IntegrityError at INSERT time. (ok() has no such
    requirement: an OK run may have a NULL revision_id.)"""

    def test_failed_run_must_carry_an_error_category(self):
        # FAIL => error_category: the factory makes it a required argument.
        with self.assertRaises(TypeError):
            RunResult.fail(trigger_source="WEB", duration_ms=1)

    def test_ok_sets_status_and_fields(self):
        run = RunResult.ok(
            revision_id=555,
            trigger_source="CRON",
            duration_ms=1500,
            sparql_engine="WDQS",
            entity_total=39163,
            grouping_count=40,
            column_count=7,
        )
        self.assertEqual(run.status, "OK")
        self.assertEqual(run.revision_id, 555)
        self.assertIsNone(run.error_category)

    def test_fail_sets_status_and_leaves_revision_none(self):
        run = RunResult.fail(
            error_category="query", trigger_source="WEB", duration_ms=1
        )
        self.assertEqual(run.status, "FAIL")
        self.assertEqual(run.error_category, "query")
        self.assertIsNone(run.revision_id)
