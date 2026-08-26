"""Database connection and schema management."""

import logging
import os
from pathlib import Path

from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _read_schema():
    """Read the SQL schema file and split into individual statements.

    Splits naively on semicolons. Safe for DDL-only schema files (CREATE TABLE,
    CREATE INDEX) but would break on statements containing literal semicolons.
    """
    return [stmt.strip() for stmt in SCHEMA_PATH.read_text().split(";") if stmt.strip()]


def get_connection():
    """Get a DB connection − ToolsDB in prod, local MariaDB in dev.

    On Toolforge, uses the ``toolforge`` helper library which reads
    credentials from ~/replica.my.cnf automatically.

    Locally, connects to a MariaDB instance configured via environment
    variables (typically from docker-compose).

    Returns a connection with DictCursor so queries return dicts.
    """
    replica_cnf = Path.home() / "replica.my.cnf"
    if replica_cnf.exists():
        import toolforge

        db_name = os.environ.get("DB_NAME", "s54041__integraality_p")
        return toolforge.toolsdb(db_name, cursorclass=DictCursor)

    import pymysql

    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "integraality"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "integraality"),
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


def ensure_schema(conn):
    """Create the tables and indexes if they don't exist."""
    with conn.cursor() as cur:
        for statement in _read_schema():
            cur.execute(statement)
    conn.commit()
