"""Full-history backfill of dashboard_configurations via a forward walk.

Replays each dashboard page's revisions in order, inserting a config row on
every hash transition and linking each bot run to the config live at its
revision. Idempotent, all-actor, graceful-NULL on parser drift. See the commit
message for the algorithm and invariants.
"""

import argparse
import datetime
import logging

import mwparserfromhell
import pywikibot
from pywikibot.data import api

from .config_assembler import ConfigAssembler, ConfigAssemblyException
from .config_facets import build_config_facets
from .dashboard_registry import DashboardRegistry
from .grouping import UnsupportedGroupingConfigurationException
from .runs_backfiller import BOT_USERNAME

logger = logging.getLogger(__name__)

# Parser drift: a revision's old syntax does not parse/resolve under today's
# assembler (both typed config errors; a malformed grouping_threshold now
# raises ConfigAssemblyException too, not a bare ValueError). These are skipped
# for transition detection (graceful NULL); any other exception -- notably a
# facet-extraction bug -- is real and must surface.
PARSER_DRIFT_ERRORS = (
    ConfigAssemblyException,
    UnsupportedGroupingConfigurationException,
)

REV_BATCH = 50
TEMPLATE_NAME = "Property dashboard"
# Cheap presence check before the full parse: skip the pre-template prefix of a
# page's history without paying parse cost per revision.
TEMPLATE_MARKER = "{{Property dashboard"


def _slot_content(rev):
    """Main-slot wikitext (pywikibot formatversion 1 keys content under "*")."""
    return rev.get("slots", {}).get("main", {}).get("*", "")


def extract_template_params(wikitext):
    """Return the start template's params as "name=value" strings, or None.

    None when the page has no {{Property dashboard}} template at this revision
    (the marker check is done by the caller; this also returns None if the
    marker matched but no real template node parses out).
    """
    code = mwparserfromhell.parse(wikitext)
    for template in code.filter_templates():
        if template.name.matches(TEMPLATE_NAME):
            return [str(param) for param in template.params]
    return None


def build_config_facets_offline(raw_params, site_url):
    """Build ConfigFacets from a revision's raw template params, no live queries.

    The backfiller's offline adapter: parse_config yields a ParsedConfig that
    already carries the resolution-independent facts (raw grouping params +
    pre-expansion authored keys), so the hash is exact. The config is NOT
    resolved -- grouping_type stays NULL (needs a live query) and column sources
    stay as placeholders (can't expand offline), which build_config_facets drops
    from the column rows while still hashing their authored key. Raises
    ConfigAssemblyException on unparseable params.
    """
    assembler = ConfigAssembler(site_url=site_url)
    config = assembler.parse_config(raw_params)
    return build_config_facets(config)


class ConfigBackfiller:
    """Forward-walk backfill of dashboard_configurations + run links."""

    def __init__(self, site):
        self.site = site
        self.config_assembler = ConfigAssembler(site_url=site.hostname())

    @property
    def site_hostname(self):
        return self.site.hostname()

    def _all_revisions(self, title):
        """Yield (revid, timestamp, user, is_bot, content) oldest->newest.

        All actors (no rvuser filter): authors are precisely the non-bot edits.
        rvdir=newer walks chronologically so the forward walk falls out of the
        iteration order.
        """
        generator = api.PropertyGenerator(
            "revisions",
            site=self.site,
            parameters={
                "titles": title,
                "rvlimit": REV_BATCH,
                "rvprop": "ids|timestamp|user|content",
                "rvslots": "main",
                "rvdir": "newer",
            },
        )
        for page in generator:
            for rev in page.get("revisions", []):
                user = rev.get("user", "")
                yield (
                    rev["revid"],
                    rev["timestamp"],
                    user,
                    user == BOT_USERNAME,
                    _slot_content(rev),
                )

    @staticmethod
    def _timestamp_to_datetime_str(iso_timestamp):
        """ISO-8601 API timestamp -> naive-UTC DATETIME string (parsed, strict)."""
        parsed = datetime.datetime.strptime(iso_timestamp, "%Y-%m-%dT%H:%M:%SZ")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    def _facets_for_revision(self, content):
        """Build offline ConfigFacets for a revision, or None.

        None when the template is absent (cheap marker check) or the params do
        not parse under today's assembler (parser drift -- graceful NULL).
        """
        if TEMPLATE_MARKER not in content:
            return None
        params = extract_template_params(content)
        if not params:
            return None
        raw = self.config_assembler.parse_config_from_params(params)
        try:
            return build_config_facets_offline(raw, site_url=self.site_hostname)
        except PARSER_DRIFT_ERRORS as e:
            # Old syntax today's assembler can't parse/resolve: skip this
            # revision for transition detection (a NULL hole in the timeline).
            # Warning, not debug, so holes are auditable after a backfill run.
            logger.warning(
                "Skipping unparseable revision for transition detection: %s", e
            )
            return None

    def backfill_dashboard(self, registry, title, dashboard_id):
        """Forward-walk one dashboard. Returns (configs_inserted, runs_linked)."""
        current_hash = None
        current_config_id = None
        configs_inserted = 0
        runs_linked = 0
        for revid, timestamp, author, is_bot, content in self._all_revisions(title):
            facets = self._facets_for_revision(content)
            if facets is not None and facets.config_hash != current_hash:
                # Hash transition: this revision authored a new config.
                config_id = registry.record_backfilled_configuration(
                    dashboard_id,
                    facets,
                    introduced_by_rev_id=revid,
                    introduced_at=self._timestamp_to_datetime_str(timestamp),
                    author=author,
                )
                if config_id != current_config_id:
                    configs_inserted += 1
                current_hash = facets.config_hash
                current_config_id = config_id
            # A bot edit is a run under the live config; link it (matched by
            # revision_id). Flat combined condition (link only fires when a run
            # is both a bot edit and a config is live).
            if (
                is_bot
                and current_config_id is not None
                and registry.link_run_to_configuration(revid, current_config_id)
            ):
                runs_linked += 1
        registry.conn.commit()
        return configs_inserted, runs_linked

    def backfill_configurations(self, limit=None):
        """Forward-walk every registered dashboard on this wiki.

        Each dashboard runs through its own short-lived DashboardRegistry
        (connection), so a long crawl never outlives ToolsDB's idle timeout and
        one failure can't poison the batch. Returns (configs, runs_linked).
        """
        with DashboardRegistry() as registry:
            dashboards = registry.list_dashboards_for_backfill(self.site_hostname)
        if not dashboards:
            logger.info("No dashboards on %s; nothing to backfill", self.site_hostname)
            return (0, 0)
        if limit is not None:
            dashboards = dashboards[:limit]
        logger.info(
            "Config forward-walk for %d dashboards on %s",
            len(dashboards),
            self.site_hostname,
        )
        total_configs = 0
        total_links = 0
        failed = 0
        for i, (title, dashboard_id, _wiki_id) in enumerate(dashboards, start=1):
            logger.info("[%d/%d] Walking %s...", i, len(dashboards), title)
            try:
                with DashboardRegistry() as registry:
                    configs, links = self.backfill_dashboard(
                        registry, title, dashboard_id
                    )
                total_configs += configs
                total_links += links
            except Exception as e:
                failed += 1
                logger.warning("Failed to backfill config for %s: %s", title, e)
        logger.info(
            "Done on %s: %d configs, %d runs linked, %d dashboards failed",
            self.site_hostname,
            total_configs,
            total_links,
            failed,
        )
        return (total_configs, total_links)


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Backfill dashboard_configurations by replaying each "
        "dashboard's full revision history (forward walk)"
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
    ConfigBackfiller(site).backfill_configurations(limit=args.limit)


if __name__ == "__main__":
    main()
