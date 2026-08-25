"""Registry for dashboard metadata — write during bot runs, read for /browse."""

import logging

from .db import ensure_schema, get_connection

logger = logging.getLogger(__name__)


class DashboardRegistry:
    """Read/write dashboard metadata to ToolsDB (or local MariaDB)."""

    def __init__(self, conn=None):
        self._conn = conn
        # Wiki cache for this run, keyed by hostname -> (id, name). Loaded
        # lazily on the first wiki resolution (None = not loaded yet), so
        # read-only uses (/browse) never trigger the load. Resolving from
        # memory avoids the ~1,400 redundant round-trips per crawl and the
        # AUTO_INCREMENT gap-burn (an upsert-on-existing burns an id).
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
        """Preload the wikis dimension table into memory (once per run).

        wikis is a tiny dimension table (a handful of rows), so a single
        SELECT is cheap and lets subsequent resolutions be pure in-memory —
        with no upsert, so an already-existing wiki burns no AUTO_INCREMENT id.
        """
        sql = "SELECT id, hostname, name FROM wikis"
        with self.conn.cursor() as cur:
            cur.execute(sql)
            self._wiki_cache = {
                row["hostname"]: (row["id"], row["name"]) for row in cur.fetchall()
            }

    def _get_or_create_wiki(self, site_hostname, site_name):
        """Return the wikis.id for a hostname, creating the row if new.

        Wiki identity is the hostname (unique). The cache is preloaded lazily
        on first use; an existing wiki resolves from memory (no write, no id
        burn), a new one is INSERTed exactly once, and a changed display name
        is refreshed with a targeted UPDATE (self-heal, still no id burn).
        """
        if self._wiki_cache is None:
            self._load_wiki_cache()

        if site_hostname in self._wiki_cache:
            wiki_id, cached_name = self._wiki_cache[site_hostname]
            if cached_name != site_name:
                # Display name changed on-wiki: refresh it (UPDATE allocates
                # no id, so no burn).
                with self.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE wikis SET name = %s WHERE id = %s",
                        (site_name, wiki_id),
                    )
                self._wiki_cache[site_hostname] = (wiki_id, site_name)
            return wiki_id

        # Genuine miss = a new wiki: one INSERT, consuming exactly one id.
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO wikis (hostname, name) VALUES (%s, %s)",
                (site_hostname, site_name),
            )
            wiki_id = cur.lastrowid
        self._wiki_cache[site_hostname] = (wiki_id, site_name)
        return wiki_id

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

        Resolves the wiki (get-or-create by hostname) and upserts the dashboard
        on the (wiki_id, page_id) unique key, refreshing the mutable display
        and browse-dimension columns (page_url, page_title, namespace_*,
        root_page). page_id is stable across renames and definition edits, so a
        dashboard keeps its identity (and, later, its run history); a
        move/rename updates the mutable columns in place.
        """
        wiki_id = self._get_or_create_wiki(site_hostname, site_name)
        sql = """\
            INSERT INTO dashboards
                (wiki_id, page_id, page_url, page_title,
                 namespace_canonical, namespace_localized, root_page)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                page_url = VALUES(page_url),
                page_title = VALUES(page_title),
                namespace_canonical = VALUES(namespace_canonical),
                namespace_localized = VALUES(namespace_localized),
                root_page = VALUES(root_page)
        """
        with self.conn.cursor() as cur:
            cur.execute(
                sql,
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
        self.conn.commit()

    def list_dashboards(self, site_hostname=None):
        """Return all registered dashboards, optionally filtered by wiki.

        Joins wikis and aliases hostname/name back to site_hostname/site_name
        so callers and templates keep a stable shape.
        """
        base = """\
            SELECT
                d.page_url AS page_url,
                d.page_title AS page_title,
                w.hostname AS site_hostname,
                w.name AS site_name
            FROM dashboards AS d
            JOIN wikis AS w ON w.id = d.wiki_id
        """
        if site_hostname:
            sql = (
                base
                + """\
                WHERE w.hostname = %s
                ORDER BY d.page_title
            """
            )
            with self.conn.cursor() as cur:
                cur.execute(sql, (site_hostname,))
                return cur.fetchall()
        else:
            sql = base + "ORDER BY d.page_title\n"
            with self.conn.cursor() as cur:
                cur.execute(sql)
                return cur.fetchall()

    def list_wikis(self):
        """Return known wikis with their dashboard counts.

        LEFT JOIN so a wiki with zero dashboards can still appear. Returns the
        stable site_hostname/site_name/count keys.
        """
        sql = """\
            SELECT
                w.hostname AS site_hostname,
                w.name AS site_name,
                COUNT(d.id) AS count
            FROM wikis AS w
            LEFT JOIN dashboards AS d ON d.wiki_id = w.id
            GROUP BY w.id, w.hostname, w.name
            ORDER BY count DESC
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
