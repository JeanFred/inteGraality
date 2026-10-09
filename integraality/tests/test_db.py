"""Tests for db module."""

import re
import unittest
from unittest.mock import MagicMock, patch

from pymysql.cursors import DictCursor

from ..db import _read_schema, ensure_schema, get_connection


class TestReadSchema(unittest.TestCase):
    def test_returns_non_empty_list(self):
        result = _read_schema()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_no_empty_statements(self):
        result = _read_schema()
        for stmt in result:
            self.assertTrue(stmt.strip())

    def test_contains_create_table(self):
        result = _read_schema()
        create_table = [s for s in result if "CREATE TABLE" in s]
        self.assertGreater(len(create_table), 0)

    def test_statements_are_valid_sql_keywords(self):
        """Each statement should start with a recognized DDL keyword."""
        result = _read_schema()
        valid_prefixes = ("CREATE", "ALTER", "DROP")
        for stmt in result:
            self.assertTrue(
                stmt.upper().startswith(valid_prefixes),
                f"Unexpected statement: {stmt[:50]}",
            )

    def test_no_inline_semicolons_in_ddl(self):
        """`_read_schema` splits on ';', so a ';' anywhere but a statement
        terminator (notably in a trailing comment) silently truncates the
        table. Guard the whole file, not just one table."""
        from ..db import SCHEMA_PATH

        for lineno, line in enumerate(SCHEMA_PATH.read_text().splitlines(), start=1):
            if ";" in line and not line.rstrip().endswith(";"):
                self.fail(f"Inline ';' on schema line {lineno}: {line.strip()!r}")


class TestDashboardRunsTable(unittest.TestCase):
    """The dashboard_runs table must parse cleanly under the naive splitter.

    _read_schema splits on ';', so the DDL must contain no inline semicolons
    and must round-trip as exactly one CREATE statement. These assertions guard
    that the table is present and well-formed without pinning every column
    (mirroring the generic, structural style of the other schema tests).
    """

    def _dashboard_runs_stmt(self):
        stmts = [s for s in _read_schema() if "EXISTS dashboard_runs (" in s]
        self.assertEqual(
            len(stmts), 1, "dashboard_runs should be exactly one statement"
        )
        return stmts[0]

    def test_is_a_single_create_table(self):
        stmt = self._dashboard_runs_stmt()
        self.assertTrue(stmt.upper().startswith("CREATE TABLE"))
        self.assertIn("IF NOT EXISTS", stmt.upper())

    def test_foreign_keys_into_spine(self):
        stmt = self._dashboard_runs_stmt()
        self.assertIn("REFERENCES dashboards (id)", stmt)
        self.assertIn("REFERENCES wikis (id)", stmt)

    def test_revision_id_is_unique_for_backfill_idempotency(self):
        stmt = self._dashboard_runs_stmt()
        self.assertIn("uq_revision", stmt)

    def test_status_is_a_closed_enum(self):
        stmt = self._dashboard_runs_stmt()
        self.assertIn("ENUM('OK', 'FAIL')", stmt)

    def test_links_to_configuration(self):
        stmt = self._dashboard_runs_stmt()
        self.assertIn("configuration_id", stmt)
        self.assertIn("REFERENCES dashboard_configurations (id)", stmt)

    def test_configuration_tables_declared_before_runs(self):
        # dashboard_runs FKs into dashboard_configurations, so the config table
        # must be created first (no ALTER needed).
        names = []
        for stmt in _read_schema():
            match = re.search(r"EXISTS (\w+) \(", stmt)
            if match:
                names.append(match.group(1))
        self.assertLess(
            names.index("dashboard_configurations"), names.index("dashboard_runs")
        )

    def test_schema_has_no_alter_statements(self):
        # Everything is additive CREATE TABLE IF NOT EXISTS -- no ALTER to make
        # ensure_schema non-idempotent across restarts.
        self.assertEqual(
            [s for s in _read_schema() if s.upper().startswith("ALTER")], []
        )


class TestPagesTable(unittest.TestCase):
    """pages: the shared wiki-page dimension."""

    def _stmt(self):
        stmts = [s for s in _read_schema() if "EXISTS pages (" in s]
        self.assertEqual(len(stmts), 1)
        return stmts[0]

    def test_is_a_single_create_table(self):
        stmt = self._stmt()
        self.assertTrue(stmt.upper().startswith("CREATE TABLE"))

    def test_identity_is_wiki_scoped_page(self):
        stmt = self._stmt()
        self.assertIn("uq_wiki_page", stmt)
        self.assertIn("REFERENCES wikis (id)", stmt)

    def test_owns_page_metadata(self):
        stmt = self._stmt()
        for col in ("page_url", "page_title", "namespace_canonical", "root_page"):
            self.assertIn(col, stmt)


class TestDashboardsTable(unittest.TestCase):
    """dashboards: thin specialization of pages."""

    def _stmt(self):
        stmts = [s for s in _read_schema() if "EXISTS dashboards (" in s]
        self.assertEqual(len(stmts), 1)
        return stmts[0]

    def test_is_thin_page_specialization(self):
        stmt = self._stmt()
        self.assertIn("page_pk", stmt)
        self.assertIn("REFERENCES pages (id)", stmt)
        self.assertIn("uq_page", stmt)


class TestDashboardConfigurationsTable(unittest.TestCase):
    """dashboard_configurations: append-only config history, hash-keyed."""

    def _stmt(self):
        stmts = [s for s in _read_schema() if "EXISTS dashboard_configurations (" in s]
        self.assertEqual(len(stmts), 1)
        return stmts[0]

    def test_is_a_single_create_table(self):
        stmt = self._stmt()
        self.assertTrue(stmt.upper().startswith("CREATE TABLE"))
        self.assertIn("IF NOT EXISTS", stmt.upper())

    def test_identity_is_dashboard_scoped_hash(self):
        stmt = self._stmt()
        self.assertIn("uq_dashboard_config", stmt)
        self.assertIn("config_hash", stmt)
        self.assertIn("REFERENCES dashboards (id)", stmt)

    def test_owns_grouping_and_selector_facets(self):
        stmt = self._stmt()
        for col in (
            "grouping_predicate",
            "grouping_property",
            "grouping_type",
            "selector_sparql",
            "selector_mentions",
            "explicit_groupings",
        ):
            self.assertIn(col, stmt)

    def test_indexes_adoption_facets(self):
        stmt = self._stmt()
        self.assertIn("idx_grouping_property", stmt)
        self.assertIn("idx_grouping_type", stmt)


class TestDashboardConfigurationColumnsTable(unittest.TestCase):
    """dashboard_configuration_columns: expanded per-config columns."""

    def _stmt(self):
        stmts = [
            s for s in _read_schema() if "EXISTS dashboard_configuration_columns (" in s
        ]
        self.assertEqual(len(stmts), 1)
        return stmts[0]

    def test_is_a_single_create_table(self):
        stmt = self._stmt()
        self.assertTrue(stmt.upper().startswith("CREATE TABLE"))

    def test_cascades_from_configuration(self):
        stmt = self._stmt()
        self.assertIn("REFERENCES dashboard_configurations (id)", stmt)
        self.assertIn("ON DELETE CASCADE", stmt)

    def test_owns_column_facets_and_provenance(self):
        stmt = self._stmt()
        for col in (
            "position",
            "column_type",
            "property_id",
            "qualifier_id",
            "value",
            "value_item",
            "value_traversal",
            "reference_check_kind",
            "reference_check_tokens",
            "source_property",
            "source_item",
            "raw_key",
        ):
            self.assertIn(col, stmt)

    def test_indexes_value_and_qualifier_facets(self):
        stmt = self._stmt()
        self.assertIn("idx_qualifier_id", stmt)
        self.assertIn("idx_value_item", stmt)


class TestSchemaOrdering(unittest.TestCase):
    """FK statement order is load-bearing for ensure_schema (top-to-bottom)."""

    def test_config_tables_follow_dashboards_in_fk_order(self):
        names = []
        for stmt in _read_schema():
            match = re.search(r"EXISTS (\w+) \(", stmt)
            if match:
                names.append(match.group(1))
        self.assertLess(
            names.index("dashboards"), names.index("dashboard_configurations")
        )
        self.assertLess(
            names.index("dashboard_configurations"),
            names.index("dashboard_configuration_columns"),
        )


class TestEnsureSchema(unittest.TestCase):
    def test_executes_all_statements(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        ensure_schema(mock_conn)

        # Should execute all statements from schema.sql
        self.assertEqual(mock_cursor.execute.call_count, len(_read_schema()))
        mock_conn.commit.assert_called_once()


class TestGetConnection(unittest.TestCase):
    """Test connection routing based on replica.my.cnf presence.

    Caller is responsible for closing the returned connection.
    """

    @patch("integraality.db.Path.home")
    def test_toolforge_connection(self, mock_home):
        mock_home_path = MagicMock()
        mock_home.return_value = mock_home_path
        (mock_home_path / "replica.my.cnf").exists.return_value = True

        mock_toolforge = MagicMock()
        mock_conn = MagicMock()
        mock_toolforge.toolsdb.return_value = mock_conn

        with patch.dict("sys.modules", {"toolforge": mock_toolforge}):
            conn = get_connection()
            mock_toolforge.toolsdb.assert_called_once_with(
                "s54041__integraality_p", cursorclass=DictCursor
            )
            self.assertEqual(conn, mock_conn)

    @patch("integraality.db.Path.home")
    @patch.dict(
        "os.environ",
        {
            "DB_HOST": "myhost",
            "DB_PORT": "3307",
            "DB_USER": "myuser",
            "DB_PASSWORD": "mypass",
            "DB_NAME": "mydb",
        },
        clear=False,
    )
    def test_local_connection(self, mock_home):
        mock_home_path = MagicMock()
        mock_home.return_value = mock_home_path
        (mock_home_path / "replica.my.cnf").exists.return_value = False

        mock_pymysql = MagicMock()
        mock_conn = MagicMock()
        mock_pymysql.connect.return_value = mock_conn

        with patch.dict(
            "sys.modules",
            {"pymysql": mock_pymysql, "pymysql.cursors": mock_pymysql.cursors},
        ):
            conn = get_connection()
            mock_pymysql.connect.assert_called_once_with(
                host="myhost",
                port=3307,
                user="myuser",
                password="mypass",
                database="mydb",
                charset="utf8mb4",
                cursorclass=DictCursor,
            )
            self.assertEqual(conn, mock_conn)

    @patch("integraality.db.Path.home")
    def test_local_connection_defaults(self, mock_home):
        """Without env vars, falls back to localhost defaults."""
        mock_home_path = MagicMock()
        mock_home.return_value = mock_home_path
        (mock_home_path / "replica.my.cnf").exists.return_value = False

        mock_pymysql = MagicMock()
        mock_conn = MagicMock()
        mock_pymysql.connect.return_value = mock_conn

        # Remove DB_ vars to test defaults
        with patch.dict("os.environ", {}, clear=False):
            import os

            for key in list(os.environ):
                if key.startswith("DB_"):
                    os.environ.pop(key, None)
            with patch.dict(
                "sys.modules",
                {"pymysql": mock_pymysql, "pymysql.cursors": mock_pymysql.cursors},
            ):
                get_connection()
                call_kwargs = mock_pymysql.connect.call_args[1]
                self.assertEqual(call_kwargs["host"], "localhost")
                self.assertEqual(call_kwargs["port"], 3306)
                self.assertEqual(call_kwargs["user"], "integraality")
                self.assertEqual(call_kwargs["database"], "integraality")
