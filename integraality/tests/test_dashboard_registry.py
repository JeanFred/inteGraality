# -*- coding: utf-8  -*-
"""Tests for dashboard_registry module."""

import unittest
from unittest.mock import MagicMock, patch

from ..dashboard_registry import DashboardRegistry


class TestDashboardRegistry(unittest.TestCase):
    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=self.mock_cursor
        )
        self.mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        self.registry = DashboardRegistry(conn=self.mock_conn)

    def test_record(self):
        # Empty wikis table preload → the wiki is a genuine miss → INSERT.
        self.mock_cursor.fetchall.return_value = []
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

        # Three statements: wiki preload SELECT, wiki INSERT, dashboard upsert.
        self.assertEqual(self.mock_cursor.execute.call_count, 3)
        wiki_preload = self.mock_cursor.execute.call_args_list[0][0]
        wiki_insert = self.mock_cursor.execute.call_args_list[1][0]
        dash_upsert = self.mock_cursor.execute.call_args_list[2][0]

        self.assertIn("SELECT id, hostname, name FROM wikis", wiki_preload[0])

        self.assertIn("INSERT INTO wikis", wiki_insert[0])
        self.assertEqual(wiki_insert[1], ("www.wikidata.org", "Wikidata"))

        self.assertIn("INSERT INTO dashboards", dash_upsert[0])
        self.assertIn("ON DUPLICATE KEY UPDATE", dash_upsert[0])
        self.assertEqual(
            dash_upsert[1],
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

    def test_record_upserts_display_columns(self):
        """The dashboard upsert refreshes mutable display columns, not the key."""
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.lastrowid = 7

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
        dash_upsert_sql = self.mock_cursor.execute.call_args_list[-1][0][0]
        update_clause = dash_upsert_sql.split("ON DUPLICATE KEY UPDATE", 1)[1]
        self.assertIn("page_url = VALUES(page_url)", update_clause)
        self.assertIn("page_title = VALUES(page_title)", update_clause)
        # Derived browse dimensions are refreshed too (mutable on rename/move).
        self.assertIn(
            "namespace_canonical = VALUES(namespace_canonical)", update_clause
        )
        self.assertIn(
            "namespace_localized = VALUES(namespace_localized)", update_clause
        )
        self.assertIn("root_page = VALUES(root_page)", update_clause)
        # Key columns are not refreshed.
        self.assertNotIn("wiki_id =", update_clause)
        self.assertNotIn("page_id =", update_clause)

    def _record(self, hostname, page_id, site_name):
        self.registry.record(
            site_hostname=hostname,
            page_id=page_id,
            page_url="https://%s/wiki/P%d" % (hostname, page_id),
            page_title="P%d" % page_id,
            site_name=site_name,
            namespace_canonical="Project",
            namespace_localized=site_name,
            root_page="P%d" % page_id,
        )

    def test_wiki_preloaded_once_then_cached(self):
        """The wikis table is preloaded once; later records touch no wiki SQL."""
        # Preload finds the wiki already present → resolves from memory, no write.
        self.mock_cursor.fetchall.return_value = [
            {"id": 7, "hostname": "www.wikidata.org", "name": "Wikidata"},
        ]

        self._record("www.wikidata.org", 1, "Wikidata")
        self._record("www.wikidata.org", 2, "Wikidata")
        self._record("www.wikidata.org", 3, "Wikidata")

        executed = [c[0][0] for c in self.mock_cursor.execute.call_args_list]
        # Exactly one preload SELECT, and no wiki writes at all (existing wiki).
        self.assertEqual(
            sum("SELECT id, hostname, name FROM wikis" in sql for sql in executed), 1
        )
        self.assertEqual(sum("INSERT INTO wikis" in sql for sql in executed), 0)
        self.assertEqual(sum("UPDATE wikis" in sql for sql in executed), 0)
        # Each record still does its own dashboards upsert, using the cached id.
        dash_calls = [
            c[0]
            for c in self.mock_cursor.execute.call_args_list
            if "INSERT INTO dashboards" in c[0][0]
        ]
        self.assertEqual(len(dash_calls), 3)
        self.assertTrue(all(call[1][0] == 7 for call in dash_calls))
        # Each record() commits its own transaction.
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
        # No filters passed → no WHERE clause.
        self.assertNotIn("WHERE", executed_sql)
        self.assertEqual(len(results), 2)

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
        self.assertEqual(params, ("meta.wikimedia.org",))
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
        self.assertIn("GROUP BY d.namespace_canonical", sql)
        self.assertIn("ORDER BY count DESC", sql)
        # No wiki filter passed → no WHERE clause.
        self.assertNotIn("WHERE", sql)

    def test_list_dashboards_filtered_by_namespace(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(namespace_canonical="User")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("d.namespace_canonical = %s", sql)
        self.assertEqual(params, ("User",))

    def test_list_dashboards_filtered_by_main_namespace(self):
        """Passing "" filters to the Main namespace (empty canonical name).

        This pins the `is not None` contract: a regression to a truthiness
        check (`if namespace_canonical:`) would silently drop this filter.
        """
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(namespace_canonical="")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("d.namespace_canonical = %s", sql)
        self.assertEqual(params, ("",))

    def test_list_dashboards_no_namespace_filter_when_none(self):
        """namespace_canonical=None applies no namespace filter."""
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(namespace_canonical=None)

        sql = self.mock_cursor.execute.call_args[0][0]
        self.assertNotIn("d.namespace_canonical = %s", sql)

    def test_list_wikis_filtered_by_namespace(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_wikis(namespace_canonical="User")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("d.namespace_canonical = %s", sql)
        self.assertEqual(params, ("User",))

    def test_list_wikis_filtered_by_main_namespace(self):
        """list_wikis also honours "" as the Main namespace (is not None)."""
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_wikis(namespace_canonical="")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("d.namespace_canonical = %s", sql)
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
        self.assertIn("d.namespace_canonical = %s", sql)
        self.assertEqual(params, ("www.wikidata.org", "Project"))

    def test_list_dashboards_filtered_by_root(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(root_page="WikiProject Music")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("d.root_page = %s", sql)
        self.assertEqual(params, ("WikiProject Music",))

    def test_list_dashboards_search_uses_like(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(search="coverage")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn(r"d.page_title LIKE %s ESCAPE '\'", sql)
        self.assertEqual(params, ("%coverage%",))

    def test_list_dashboards_search_escapes_wildcards(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(search="100%_done")

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn(r"ESCAPE '\'", sql)
        self.assertEqual(params, (r"%100\%\_done%",))

    def test_list_dashboards_combined_filters(self):
        self.mock_cursor.fetchall.return_value = []

        self.registry.list_dashboards(
            site_hostname="www.wikidata.org",
            namespace_canonical="Project",
            root_page="WikiProject Music",
            search="album",
        )

        sql, params = self.mock_cursor.execute.call_args[0]
        # Assert each condition is present and the params are exact — durable
        # checks, unlike counting " AND " occurrences.
        self.assertIn("w.hostname = %s", sql)
        self.assertIn("d.namespace_canonical = %s", sql)
        self.assertIn("d.root_page = %s", sql)
        self.assertIn("d.page_title LIKE %s", sql)
        self.assertEqual(
            params,
            ("www.wikidata.org", "Project", "WikiProject Music", "%album%"),
        )

    def test_list_roots(self):
        self.mock_cursor.fetchall.return_value = [
            {"root_page": "Jean-Fred"},
            {"root_page": "WikiProject Music"},
        ]

        results = self.registry.list_roots()

        sql = self.mock_cursor.execute.call_args[0][0]
        self.assertIn("SELECT DISTINCT d.root_page", sql)
        self.assertEqual(results, ["Jean-Fred", "WikiProject Music"])

    def test_list_dashboards_missing_page_metadata(self):
        """Filters on page_created_at IS NULL (the reliably-present field),
        not page_creator (which can be suppressed), and always scopes to the
        given wiki."""
        self.mock_cursor.fetchall.return_value = [
            {"id": 1, "page_title": "Foo", "site_hostname": "www.wikidata.org"},
        ]

        results = self.registry.list_dashboards_missing_page_metadata(
            site_hostname="www.wikidata.org"
        )

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("d.page_created_at IS NULL", sql)
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
        self.assertIn("d.page_created_at IS NULL", sql)
        self.assertIn("w.hostname = %s", sql)
        self.assertEqual(params, ("meta.wikimedia.org",))

    def test_update_page_metadata(self):
        self.registry.update_page_metadata(
            dashboard_id=42,
            page_creator="Alice",
            page_created_at="2020-01-02T03:04:05Z",
        )

        sql, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("UPDATE dashboards", sql)
        self.assertIn("page_creator = %s", sql)
        self.assertIn("page_created_at = %s", sql)
        self.assertIn("WHERE id = %s", sql)
        self.assertEqual(params, ("Alice", "2020-01-02T03:04:05Z", 42))
        self.mock_conn.commit.assert_called_once()

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
