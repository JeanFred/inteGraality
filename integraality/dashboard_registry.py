"""Registry for dashboard metadata — write during bot runs, read for /browse."""

import datetime
import logging
from dataclasses import dataclass

from .db import ensure_schema, get_connection

logger = logging.getLogger(__name__)

# How many recent runs the /dashboards health strip shows per dashboard.
RECENT_RUNS_STRIP_SIZE = 12
# Consecutive failures at/above which a dashboard is "chronically" broken
# (strong tint) rather than a possibly-transient blip (light tint).
CHRONIC_FAILURE_THRESHOLD = 3


@dataclass(frozen=True)
class RunResult:
    """One completed run, as recorded in dashboard_runs.

    Write-once value holder; build via ``RunResult.ok(...)`` / ``.fail(...)``,
    whose required args enforce the schema invariants at the call site.
    """

    status: str | None = None
    trigger_source: str | None = None
    duration_ms: int | None = None
    sparql_engine: str | None = None
    error_category: str | None = None
    error_detail: str | None = None
    revision_id: int | None = None
    entity_total: int | None = None
    grouping_count: int | None = None
    column_count: int | None = None

    @classmethod
    def ok(
        cls,
        *,
        revision_id,
        trigger_source,
        duration_ms,
        sparql_engine,
        entity_total,
        grouping_count,
        column_count,
    ):
        """A successful run (``revision_id`` may be None: no oldid produced)."""
        return cls(
            status="OK",
            revision_id=revision_id,
            trigger_source=trigger_source,
            duration_ms=duration_ms,
            sparql_engine=sparql_engine,
            entity_total=entity_total,
            grouping_count=grouping_count,
            column_count=column_count,
        )

    @classmethod
    def fail(
        cls,
        *,
        error_category,
        trigger_source,
        duration_ms,
        error_detail=None,
        sparql_engine=None,
    ):
        """A failed run. ``error_category`` is required (FAIL => category)."""
        return cls(
            status="FAIL",
            error_category=error_category,
            trigger_source=trigger_source,
            duration_ms=duration_ms,
            error_detail=error_detail,
            sparql_engine=sparql_engine,
        )


class DashboardRegistry:
    """Read/write dashboard metadata to ToolsDB (or local MariaDB)."""

    def __init__(self, conn=None):
        self._conn = conn
        # hostname -> (id, name), loaded lazily on first wiki resolution.
        self._wiki_cache = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = get_connection()
            ensure_schema(self._conn)
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _load_wiki_cache(self):
        """Preload the (tiny) wikis table into memory, once per run."""
        sql = "SELECT id, hostname, name FROM wikis"
        with self.conn.cursor() as cur:
            cur.execute(sql)
            self._wiki_cache = {
                row["hostname"]: (row["id"], row["name"]) for row in cur.fetchall()
            }

    def _get_or_create_wiki(self, site_hostname, site_name):
        """Return the wikis.id for a hostname, creating the row if new.

        Existing wiki resolves from the cache (no id burn); a changed display
        name self-heals via UPDATE.
        """
        if self._wiki_cache is None:
            self._load_wiki_cache()

        if site_hostname in self._wiki_cache:
            wiki_id, cached_name = self._wiki_cache[site_hostname]
            if cached_name != site_name:
                with self.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE wikis SET name = %s WHERE id = %s",
                        (site_name, wiki_id),
                    )
                self._wiki_cache[site_hostname] = (wiki_id, site_name)
            return wiki_id

        # New wiki: one INSERT.
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO wikis (hostname, name) VALUES (%s, %s)",
                (site_hostname, site_name),
            )
            wiki_id = cur.lastrowid
        self._wiki_cache[site_hostname] = (wiki_id, site_name)
        return wiki_id

    def _get_or_create_page(
        self,
        wiki_id,
        page_id,
        page_url,
        page_title,
        namespace_canonical,
        namespace_localized,
        root_page,
    ):
        """Return the pages.id for a (wiki, page_id), creating/refreshing it.

        Read-then-targeted-UPDATE (not INSERT ... ON DUPLICATE KEY) so
        re-recording burns no AUTO_INCREMENT id. Creation columns
        (page_creator/page_created_at) are left to the backfiller.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM pages WHERE wiki_id = %s AND page_id = %s",
                (wiki_id, page_id),
            )
            row = cur.fetchone()
            if row is not None:
                pages_id = row["id"]
                cur.execute(
                    """\
                    UPDATE pages
                    SET page_url = %s, page_title = %s,
                        namespace_canonical = %s, namespace_localized = %s,
                        root_page = %s
                    WHERE id = %s
                    """,
                    (
                        page_url,
                        page_title,
                        namespace_canonical,
                        namespace_localized,
                        root_page,
                        pages_id,
                    ),
                )
                return pages_id

            cur.execute(
                """\
                INSERT INTO pages
                    (wiki_id, page_id, page_url, page_title,
                     namespace_canonical, namespace_localized, root_page)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    wiki_id,
                    page_id,
                    page_url,
                    page_title,
                    namespace_canonical,
                    namespace_localized,
                    root_page,
                ),
            )
            return cur.lastrowid

    def record(
        self,
        site_hostname,
        page_id,
        page_url,
        page_title,
        site_name,
        namespace_canonical,
        namespace_localized,
        root_page,
    ):
        """Record a dashboard, keyed on its stable (wiki, page_id).

        Resolves the wiki and shared pages row, then ensures a dashboards row.
        page_id is stable across renames, so identity (and run history) survives
        a move.
        """
        wiki_id = self._get_or_create_wiki(site_hostname, site_name)
        page_pk = self._get_or_create_page(
            wiki_id,
            page_id,
            page_url,
            page_title,
            namespace_canonical,
            namespace_localized,
            root_page,
        )
        self._get_or_create_dashboard(page_pk)
        self.conn.commit()

    def _get_or_create_dashboard(self, page_pk):
        """Return the dashboards.id for a page, creating the row if new.

        Read-then-write on the unique page_pk, so an existing dashboard burns no
        AUTO_INCREMENT id on re-record.
        """
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM dashboards WHERE page_pk = %s", (page_pk,))
            row = cur.fetchone()
            if row is not None:
                return row["id"]
            cur.execute("INSERT INTO dashboards (page_pk) VALUES (%s)", (page_pk,))
            return cur.lastrowid

    @staticmethod
    def _utc_now_str():
        """Naive-UTC DATETIME string, matching the schema's DATETIME columns."""
        return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")

    def record_run(self, page_metadata, run: "RunResult"):
        """Append one completed run for a dashboard.

        Resolves wiki/page/dashboard from ``page_metadata`` (get-or-create, so
        an unregistered page still records), then INSERTs the ``run``.
        finished_at is stamped here in naive UTC. Append-only.
        """
        wiki_id = self._get_or_create_wiki(
            page_metadata["site_hostname"], page_metadata["site_name"]
        )
        page_pk = self._get_or_create_page(
            wiki_id,
            page_metadata["page_id"],
            page_metadata["page_url"],
            page_metadata["page_title"],
            page_metadata["namespace_canonical"],
            page_metadata["namespace_localized"],
            page_metadata["root_page"],
        )
        dashboard_id = self._get_or_create_dashboard(page_pk)
        self._insert_run(dashboard_id, wiki_id, self._utc_now_str(), run)
        self.conn.commit()

    def _insert_run(self, dashboard_id, wiki_id, finished_at, run, ignore=False):
        """Append one dashboard_runs row; return whether a row was inserted.

        With ``ignore``, uses INSERT IGNORE so a duplicate ``revision_id`` is
        skipped (rowcount 0) instead of raising.
        """
        verb = "INSERT IGNORE" if ignore else "INSERT"
        sql = f"""\
            {verb} INTO dashboard_runs
                (dashboard_id, wiki_id, finished_at, duration_ms, status,
                 trigger_source, sparql_engine, error_category, error_detail,
                 revision_id, entity_total, grouping_count, column_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with self.conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    dashboard_id,
                    wiki_id,
                    finished_at,
                    run.duration_ms,
                    run.status,
                    run.trigger_source,
                    run.sparql_engine,
                    run.error_category,
                    run.error_detail,
                    run.revision_id,
                    run.entity_total,
                    run.grouping_count,
                    run.column_count,
                ),
            )
            return cur.rowcount > 0

    def list_dashboards_for_backfill(self, site_hostname):
        """Return this wiki's dashboards as (page_title, dashboard_id, wiki_id).

        The runs backfiller's join set: page_title to query the action API, and
        the resolved ids so it records via record_resolved_backfilled_run
        without re-resolving per revision.
        """
        sql = """\
            SELECT p.page_title AS page_title, d.id AS dashboard_id,
                   w.id AS wiki_id
            FROM dashboards AS d
            JOIN pages AS p ON p.id = d.page_pk
            JOIN wikis AS w ON w.id = p.wiki_id
            WHERE w.hostname = %s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (site_hostname,))
            return [
                (row["page_title"], row["dashboard_id"], row["wiki_id"])
                for row in cur.fetchall()
            ]

    def record_resolved_backfilled_run(
        self, dashboard_id, wiki_id, run: "RunResult", finished_at
    ):
        """Insert one historical run against already-resolved ids.

        For the runs backfiller (ids come from list_dashboards_for_backfill, so
        no get-or-create). Idempotent (INSERT IGNORE on uq_revision), requires
        ``run.revision_id``, and does NOT commit — the backfiller commits per
        dashboard. Returns whether a row was inserted.
        """
        if run.revision_id is None:
            raise ValueError("record_resolved_backfilled_run requires run.revision_id")
        return self._insert_run(dashboard_id, wiki_id, finished_at, run, ignore=True)

    def list_runs(self, site_hostname=None, limit=100):
        """Return recent runs across all dashboards, newest first (bounded by
        ``limit``). Joins page identity; carries status + run fields.
        """
        sql = """\
            SELECT
                p.page_url AS page_url,
                p.page_title AS page_title,
                w.hostname AS site_hostname,
                w.name AS site_name,
                r.finished_at AS finished_at,
                r.status AS status,
                r.trigger_source AS trigger_source,
                r.duration_ms AS duration_ms,
                r.sparql_engine AS sparql_engine,
                r.error_category AS error_category,
                r.error_detail AS error_detail,
                r.entity_total AS entity_total,
                r.grouping_count AS grouping_count,
                r.column_count AS column_count
            FROM dashboard_runs AS r
            JOIN dashboards AS d ON d.id = r.dashboard_id
            JOIN pages AS p ON p.id = d.page_pk
            JOIN wikis AS w ON w.id = r.wiki_id
        """
        params = []
        if site_hostname:
            sql += "WHERE w.hostname = %s\n"
            params.append(site_hostname)
        sql += "ORDER BY r.finished_at DESC\n"
        sql += "LIMIT %s\n"
        params.append(limit)
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def list_dashboards_missing_page_metadata(self, site_hostname):
        """Return dashboard pages missing page_created_at (id = pages.id)."""
        sql = """\
            SELECT
                p.id AS id,
                p.page_title AS page_title,
                w.hostname AS site_hostname
            FROM pages AS p
            JOIN dashboards AS d ON d.page_pk = p.id
            JOIN wikis AS w ON w.id = p.wiki_id
        """
        conditions = ["p.page_created_at IS NULL", "w.hostname = %s"]
        params = [site_hostname]
        sql += "WHERE " + " AND ".join(conditions) + "\n"
        sql += "ORDER BY p.id\n"
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def update_page_metadata(self, page_pk, page_creator, page_created_at):
        """Fill in the immutable page-creation columns for one page."""
        sql = """\
            UPDATE pages
            SET page_creator = %s, page_created_at = %s
            WHERE id = %s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (page_creator, page_created_at, page_pk))
        self.conn.commit()

    def list_dashboards(
        self,
        site_hostname=None,
        namespace_canonical=None,
        root_page=None,
        search=None,
        status=None,
    ):
        """Return all registered dashboards, optionally filtered.

        Filters (all optional, combined with AND):
          - site_hostname: exact wiki hostname
          - namespace_canonical: exact canonical namespace (pass "" to match the
            Main namespace; pass None to not filter on namespace)
          - root_page: exact root page (first title segment)
          - search: case-insensitive substring match on the page title
          - status: latest-run status ('OK'|'FAIL'); filters to dashboards whose
            most recent run has that status (never-run dashboards are excluded)

        Joins pages and wikis and aliases the columns back to the historical
        shape (page_url/page_title/namespace_*/root_page/site_hostname/
        site_name) so callers and templates keep a stable shape.

        Each row also carries its latest run (latest_status/latest_finished_at/
        latest_duration_ms), LEFT-joined (NULL when never run), picked by
        ROW_NUMBER() over (finished_at DESC, id DESC). It also carries, for the
        health strip: last_success_at (newest OK run), recent_statuses (last
        RECENT_RUNS_STRIP_SIZE run tokens, oldest->newest: FAIL, NULL for an OK
        run that produced no revision (null edit), else OK) and
        failures_since_success (runs after the last OK by (finished_at, id), so
        a same-second FAIL still counts; drives the severity tint).
        """
        sql = """\
            SELECT
                p.page_url AS page_url,
                p.page_title AS page_title,
                p.namespace_canonical AS namespace_canonical,
                p.namespace_localized AS namespace_localized,
                p.root_page AS root_page,
                w.hostname AS site_hostname,
                w.name AS site_name,
                r.status AS latest_status,
                r.finished_at AS latest_finished_at,
                r.duration_ms AS latest_duration_ms,
                ok.finished_at AS last_success_at,
                strip.statuses AS recent_statuses,
                CASE
                    WHEN ok.finished_at IS NULL THEN (
                        SELECT COUNT(*) FROM dashboard_runs f
                        WHERE f.dashboard_id = d.id
                    )
                    ELSE (
                        SELECT COUNT(*) FROM dashboard_runs f
                        WHERE f.dashboard_id = d.id
                          AND (f.finished_at, f.id) > (ok.finished_at, ok.id)
                    )
                END AS failures_since_success
            FROM dashboards AS d
            JOIN pages AS p ON p.id = d.page_pk
            JOIN wikis AS w ON w.id = p.wiki_id
            LEFT JOIN (
                SELECT
                    dashboard_id, status, finished_at, duration_ms,
                    ROW_NUMBER() OVER (
                        PARTITION BY dashboard_id
                        ORDER BY finished_at DESC, id DESC
                    ) AS rn
                FROM dashboard_runs
            ) AS r ON r.dashboard_id = d.id AND r.rn = 1
            LEFT JOIN (
                SELECT
                    dashboard_id, id, finished_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY dashboard_id
                        ORDER BY finished_at DESC, id DESC
                    ) AS rn
                FROM dashboard_runs
                WHERE status = 'OK'
            ) AS ok ON ok.dashboard_id = d.id AND ok.rn = 1
            LEFT JOIN (
                -- The last N runs per dashboard, concatenated oldest->newest
                -- into "OK,NULL,FAIL,..." for the template to render as ticks.
                -- A null edit is an OK run that produced no revision
                -- (revision_id IS NULL); it stays a success for health, but is
                -- tokenised as NULL so the strip can render it distinctly.
                SELECT dashboard_id,
                       GROUP_CONCAT(
                           CASE
                               WHEN status = 'FAIL' THEN 'FAIL'
                               WHEN revision_id IS NULL THEN 'NULL'
                               ELSE 'OK'
                           END
                           ORDER BY finished_at ASC, id ASC
                       ) AS statuses
                FROM (
                    SELECT dashboard_id, status, revision_id, finished_at, id,
                           ROW_NUMBER() OVER (
                               PARTITION BY dashboard_id
                               ORDER BY finished_at DESC, id DESC
                           ) AS rn
                    FROM dashboard_runs
                ) ranked
                WHERE rn <= %s
                GROUP BY dashboard_id
            ) AS strip ON strip.dashboard_id = d.id
        """
        conditions = []
        # The strip subquery's LIMIT placeholder comes first in SQL order, so
        # it must be the first bound param, ahead of any filter conditions.
        params = [RECENT_RUNS_STRIP_SIZE]
        if site_hostname:
            conditions.append("w.hostname = %s")
            params.append(site_hostname)
        if namespace_canonical is not None:
            conditions.append("p.namespace_canonical = %s")
            params.append(namespace_canonical)
        if root_page:
            conditions.append("p.root_page = %s")
            params.append(root_page)
        if search:
            # Escape SQL LIKE wildcards in user input so literal % and _ are
            # matched as-is rather than treated as pattern characters.
            escaped = search.replace("%", r"\%").replace("_", r"\_")
            conditions.append(r"p.page_title LIKE %s ESCAPE '\'")
            params.append(f"%{escaped}%")
        if status:
            # r.status is the latest run's status (LEFT JOIN); a never-run
            # dashboard has NULL here and is correctly excluded by equality.
            conditions.append("r.status = %s")
            params.append(status)
        if conditions:
            sql += "WHERE " + " AND ".join(conditions) + "\n"
        sql += "ORDER BY p.page_title\n"
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def list_wikis(self, namespace_canonical=None):
        """Return known wikis with their dashboard counts, optionally scoped
        to a namespace."""
        sql = """\
            SELECT
                w.hostname AS site_hostname,
                w.name AS site_name,
                COUNT(d.id) AS count
            FROM wikis AS w
            JOIN pages AS p ON p.wiki_id = w.id
            JOIN dashboards AS d ON d.page_pk = p.id
        """
        params = []
        if namespace_canonical is not None:
            sql += "WHERE p.namespace_canonical = %s\n"
            params.append(namespace_canonical)
        sql += """\
            GROUP BY w.id, w.hostname, w.name
            ORDER BY count DESC
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def list_namespaces(self, site_hostname=None):
        """Return distinct canonical namespaces with their dashboard counts,
        optionally scoped to a wiki."""
        sql = """\
            SELECT
                p.namespace_canonical,
                COUNT(*) AS count
            FROM dashboards AS d
            JOIN pages AS p ON p.id = d.page_pk
            JOIN wikis AS w ON w.id = p.wiki_id
        """
        params = []
        if site_hostname:
            sql += "WHERE w.hostname = %s\n"
            params.append(site_hostname)
        sql += """\
            GROUP BY p.namespace_canonical
            ORDER BY count DESC
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def list_roots(self, site_hostname=None, namespace_canonical=None):
        """Return distinct root pages, optionally scoped by active filters.

        When wiki or namespace filters are active, only suggests roots that
        exist within that filtered set — so the autocomplete stays relevant.
        """
        sql = """\
            SELECT DISTINCT p.root_page
            FROM dashboards AS d
            JOIN pages AS p ON p.id = d.page_pk
            JOIN wikis AS w ON w.id = p.wiki_id
        """
        conditions = []
        params = []
        if site_hostname:
            conditions.append("w.hostname = %s")
            params.append(site_hostname)
        if namespace_canonical is not None:
            conditions.append("p.namespace_canonical = %s")
            params.append(namespace_canonical)
        if conditions:
            sql += "WHERE " + " AND ".join(conditions) + "\n"
        sql += "ORDER BY p.root_page\n"
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return [row["root_page"] for row in cur.fetchall()]
