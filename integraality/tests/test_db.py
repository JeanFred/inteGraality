# -*- coding: utf-8  -*-
"""Tests for db module."""

import unittest
from unittest.mock import MagicMock, patch

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
            mock_toolforge.toolsdb.assert_called_once_with("s54041__integraality")
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

        with patch.dict("sys.modules", {"pymysql": mock_pymysql}):
            conn = get_connection()
            mock_pymysql.connect.assert_called_once_with(
                host="myhost",
                port=3307,
                user="myuser",
                password="mypass",
                database="mydb",
                charset="utf8mb4",
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
            with patch.dict("sys.modules", {"pymysql": mock_pymysql}):
                get_connection()
                call_kwargs = mock_pymysql.connect.call_args[1]
                self.assertEqual(call_kwargs["host"], "localhost")
                self.assertEqual(call_kwargs["port"], 3306)
                self.assertEqual(call_kwargs["user"], "integraality")
                self.assertEqual(call_kwargs["database"], "integraality")
