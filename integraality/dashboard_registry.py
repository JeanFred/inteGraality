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

    def list_dashboards_missing_page_metadata(self, site_hostname):
        """Return dashboards still missing page-creation metadata.

        Rows are "missing" when ``page_created_at IS NULL``.

        Returns (id, page_title, site_hostname) rows.
        """
        sql = """\
            SELECT
                d.id AS id,
                d.page_title AS page_title,
                w.hostname AS site_hostname
            FROM dashboards AS d
            JOIN wikis AS w ON w.id = d.wiki_id
        """
        conditions = ["d.page_created_at IS NULL", "w.hostname = %s"]
        params = [site_hostname]
        sql += "WHERE " + " AND ".join(conditions) + "\n"
        sql += "ORDER BY d.id\n"
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def update_page_metadata(self, dashboard_id, page_creator, page_created_at):
        """Fill in the immutable page-creation columns for one dashboard."""
        sql = """\
            UPDATE dashboards
            SET page_creator = %s, page_created_at = %s
            WHERE id = %s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (page_creator, page_created_at, dashboard_id))
        self.conn.commit()

    def list_dashboards(
        self,
        site_hostname=None,
        namespace_canonical=None,
        root_page=None,
        search=None,
    ):
        """Return all registered dashboards, optionally filtered.

        Filters (all optional, combined with AND):
          - site_hostname: exact wiki hostname
          - namespace_canonical: exact canonical namespace (pass "" to match the
            Main namespace; pass None to not filter on namespace)
          - root_page: exact root page (first title segment)
          - search: case-insensitive substring match on the page title

        Joins wikis and aliases hostname/name back to site_hostname/site_name
        so callers and templates keep a stable shape.
        """
        sql = """\
            SELECT
                d.page_url AS page_url,
                d.page_title AS page_title,
                d.namespace_canonical AS namespace_canonical,
                d.namespace_localized AS namespace_localized,
                d.root_page AS root_page,
                w.hostname AS site_hostname,
                w.name AS site_name
            FROM dashboards AS d
            JOIN wikis AS w ON w.id = d.wiki_id
        """
        conditions = []
        params = []
        if site_hostname:
            conditions.append("w.hostname = %s")
            params.append(site_hostname)
        if namespace_canonical is not None:
            conditions.append("d.namespace_canonical = %s")
            params.append(namespace_canonical)
        if root_page:
            conditions.append("d.root_page = %s")
            params.append(root_page)
        if search:
            # Escape SQL LIKE wildcards in user input so literal % and _ are
            # matched as-is rather than treated as pattern characters.
            escaped = search.replace("%", r"\%").replace("_", r"\_")
            conditions.append(r"d.page_title LIKE %s ESCAPE '\'")
            params.append(f"%{escaped}%")
        if conditions:
            sql += "WHERE " + " AND ".join(conditions) + "\n"
        sql += "ORDER BY d.page_title\n"
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
            JOIN dashboards AS d ON d.wiki_id = w.id
        """
        params = []
        if namespace_canonical is not None:
            sql += "WHERE d.namespace_canonical = %s\n"
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
                d.namespace_canonical,
                COUNT(*) AS count
            FROM dashboards AS d
            JOIN wikis AS w ON w.id = d.wiki_id
        """
        params = []
        if site_hostname:
            sql += "WHERE w.hostname = %s\n"
            params.append(site_hostname)
        sql += """\
            GROUP BY d.namespace_canonical
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
            SELECT DISTINCT d.root_page
            FROM dashboards AS d
            JOIN wikis AS w ON w.id = d.wiki_id
        """
        conditions = []
        params = []
        if site_hostname:
            conditions.append("w.hostname = %s")
            params.append(site_hostname)
        if namespace_canonical is not None:
            conditions.append("d.namespace_canonical = %s")
            params.append(namespace_canonical)
        if conditions:
            sql += "WHERE " + " AND ".join(conditions) + "\n"
        sql += "ORDER BY d.root_page\n"
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return [row["root_page"] for row in cur.fetchall()]
