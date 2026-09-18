"""Orchestration — reads wiki pages, triggers updates."""

import logging
import os
import re
from time import perf_counter

import mwparserfromhell
import pywikibot
from redis import StrictRedis

from .cache import RedisCache
from .config_assembler import PARAM_RENAMES, ConfigAssembler, ConfigAssemblyException
from .dashboard_registry import DashboardRegistry, RunResult
from .error_category import ErrorCategory
from .grouping import EmptyGroupingException, UnsupportedGroupingConfigurationException
from .grouping_page_creator import GroupingPageCreator
from .page_saving import save_to_wiki_or_local
from .property_statistics import PropertyStatistics
from .sparql_utils import QueryException

logger = logging.getLogger("integraality.update")


class ProcessingException(Exception):
    error_category = ErrorCategory.CONFIG


class ConfigException(ProcessingException):
    pass


class NoEndTemplateException(ProcessingException):
    pass


class NoStartTemplateException(ProcessingException):
    pass


class TransientServerException(Exception):
    """Exception for temporary server issues that may resolve on retry."""

    error_category = ErrorCategory.TRANSIENT


class UnsupportedWikiException(ConfigException):
    """The target URL is not a Wikimedia wiki (mistake or SSRF/proxy abuse)."""


# Wikis supported today: Wikidata plus Commons/Meta (*.wikimedia.org). Static
# allowlist -- a security boundary that must run at request entry with no I/O.
ALLOWED_WIKI_DOMAINS = frozenset(
    {
        "wikidata.org",
        "wikimedia.org",
    }
)


def validate_wiki_url(url):
    """Return the wiki host, or raise UnsupportedWikiException for a bad URL."""
    from urllib.parse import urlparse

    if isinstance(url, bytes):
        url = url.decode("utf-8", "replace")
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https"):
        raise UnsupportedWikiException(f"Unsupported URL scheme: {url!r}")
    host = (parsed.hostname or "").lower()
    allowed = any(
        host == domain or host.endswith("." + domain) for domain in ALLOWED_WIKI_DOMAINS
    )
    if not allowed:
        raise UnsupportedWikiException(f"Not a Wikimedia wiki URL: {url!r}")
    return host


class PagesProcessor:
    def __init__(self, url="https://www.wikidata.org/wiki/", cache_client=None):
        validate_wiki_url(url)
        self.url = url
        self._site = None
        self.template_name = "Property dashboard"
        self.end_template_name = "Property dashboard end"
        self.summary = "Update property usage stats"

        self.outputs = []
        self.config_assembler = ConfigAssembler(site_url=url)

        if not cache_client:
            host = os.getenv("REDIS_HOST", "tools-redis.svc.eqiad.wmflabs")
            cache_client = StrictRedis(host=host, decode_responses=False)
        self.cache = RedisCache(cache_client=cache_client)

    @property
    def site(self):
        if self._site is None:
            self._site = pywikibot.Site(url=self.url)
        return self._site

    @staticmethod
    def _site_code_from_url(url):
        """Derive a stable site identifier from a wiki URL."""
        from urllib.parse import urlparse

        if isinstance(url, bytes):
            url = url.decode("utf-8", "replace")
        return urlparse(url).netloc

    def make_cache_key(self, page_title):
        return ":".join([self._site_code_from_url(self.url), page_title]).replace(
            " ", "_"
        )

    def get_all_pages(self, limit=None):
        template = pywikibot.Page(self.site, self.template_name, ns=10)
        return template.getReferences(only_template_inclusion=True, total=limit)

    def make_stats_object_arguments_for_page(self, page):
        all_templates_with_params = page.templatesWithParams()

        if self.template_name not in [
            template.title(with_ns=False) for (template, _) in all_templates_with_params
        ]:
            msg = (
                f"No start template '{self.template_name}' found."
                "The likely explanation is that inteGraality was invoked from a page that transcludes the page with the template. "
                "Please invoke inteGraality directly from the page with the template."
            )
            raise NoStartTemplateException(msg)

        if self.end_template_name not in [
            template.title(with_ns=False) for (template, _) in all_templates_with_params
        ]:
            raise NoEndTemplateException(
                f"No end template '{self.end_template_name}' provided"
            )

        start_templates_with_params = [
            (template, params)
            for (template, params) in all_templates_with_params
            if template.title(with_ns=False) == self.template_name
        ]

        if len(start_templates_with_params) > 1:
            logger.warning("More than one template on the page %s", page.title())

        (template, params) = start_templates_with_params[0]
        parsed_config = self.config_assembler.parse_config_from_params(params)
        try:
            config = self.config_assembler.parse_config(parsed_config)
        except ConfigAssemblyException as e:
            raise ConfigException(e) from e
        key = self.make_cache_key(page.title())
        self.cache.set_cache_value(key, config)
        return config

    def make_stats_object_for_page(self, page):
        config = self.make_stats_object_arguments_for_page(page)
        grouping_link_mode = config.pop("grouping_link_mode", "link")
        try:
            stats = PropertyStatistics(**config)
        except TypeError:
            raise ConfigException("The template parameters are incorrect.")
        except UnsupportedGroupingConfigurationException as e:
            raise ConfigException(e) from e
        return stats, grouping_link_mode

    def process_page(self, page, trigger_source="CRON"):
        start_time = perf_counter()
        try:
            logger.debug("Invalidating cache key for %s", page.title())
            self.cache.invalidate(self.make_cache_key(page.title()))
            logger.info("Parsing page configuration...")
            stats, grouping_link_mode = self.make_stats_object_for_page(page)
            groupings = stats.retrieve_data()
            report_groupings = stats.prepare_report_groupings(groupings)
            formatter = stats.build_formatter()
            output = formatter.format_report(report_groupings)
            elapsed_time = perf_counter() - start_time
            new_text = self.replace_in_page(output, page.get())
            new_text = self.migrate_template_params(new_text)
            summary = (
                self.summary
                + f" using {stats.get_sparql_engine_name()} ({int(elapsed_time)}s)"
            )
            logger.info("Saving to wiki...")
            revision_id = save_to_wiki_or_local(page, summary, new_text)

            self._record_run_ok(
                page,
                trigger_source=trigger_source,
                elapsed_time=elapsed_time,
                stats=stats,
                groupings=groupings,
                report_groupings=report_groupings,
                revision_id=revision_id,
            )

            if grouping_link_mode == "create":
                creator = GroupingPageCreator(
                    site=self.site,
                    selector_sparql=stats.selector_sparql,
                    grouping_predicate=stats.grouping_configuration.get_predicate(),
                    columns=stats.columns,
                    page_title=page.title(),
                )
                creator.create_pages(groupings.values())

            return elapsed_time
        except (NoStartTemplateException, NoEndTemplateException):
            # The page is not a dashboard (no template). Do not record a run or
            # touch the registry -- otherwise any URL passed to /update would
            # create dashboard/registry rows for an arbitrary page.
            raise
        except Exception as e:
            # A real dashboard failed (query/config/etc.): record the FAIL run,
            # then re-raise so the outer per-page handler still logs and skips.
            self._record_run_fail(
                page,
                trigger_source=trigger_source,
                elapsed_time=perf_counter() - start_time,
                exc=e,
            )
            raise

    def _record_run_ok(
        self,
        page,
        trigger_source,
        elapsed_time,
        stats,
        groupings,
        report_groupings,
        revision_id,
    ):
        """Record a successful run. Best-effort: never break the crawl."""
        run = RunResult.ok(
            revision_id=revision_id,
            trigger_source=trigger_source,
            duration_ms=int(elapsed_time * 1000),
            sparql_engine=stats.get_sparql_engine_name(),
            entity_total=stats.get_entity_total(report_groupings),
            grouping_count=len(groupings),
            column_count=len(stats.columns),
        )
        try:
            with DashboardRegistry() as registry:
                registry.record_run(self._dashboard_metadata(page), run)
        except Exception as e:
            logger.warning("Failed to record run for %s: %s", page.title(), e)

    def _record_run_fail(self, page, trigger_source, elapsed_time, exc):
        """Record a failed run. Best-effort: never mask the original error."""
        category = getattr(exc, "error_category", None)
        # Full traceback here (both WEB and CRON reach this) -- the DB only keeps
        # a truncated one-liner.
        logger.exception(
            "Run failed for %s [%s]: %s",
            page.title(),
            category.value if category else ErrorCategory.ERROR.value,
            exc,
        )
        run = RunResult.fail(
            error_category=category.value if category else ErrorCategory.ERROR.value,
            trigger_source=trigger_source,
            duration_ms=int(elapsed_time * 1000),
            error_detail=str(exc)[:2000],
        )
        try:
            with DashboardRegistry() as registry:
                registry.record_run(self._dashboard_metadata(page), run)
        except Exception as e:
            logger.warning("Failed to record failed run for %s: %s", page.title(), e)

    def replace_in_page(self, output, page_text):
        regex_text = f"({{{{{self.template_name}.*?(?<!{{{{!)}}}}).*?({{{{{self.end_template_name}}}}})"
        regex = re.compile(regex_text, re.MULTILINE | re.DOTALL)
        new_text = re.sub(regex, rf"\1\n{output}\n\2", page_text, count=1)
        return new_text

    def migrate_template_params(self, page_text):
        """Rename deprecated template parameter names within the start template."""
        code = mwparserfromhell.parse(page_text)
        for template in code.filter_templates():
            if template.name.matches(self.template_name):
                for old, new in PARAM_RENAMES.items():
                    if template.has(old):
                        template.get(old).name = new
        return str(code)

    @staticmethod
    def _dashboard_metadata(page):
        """Derive the registry fields from a live pywikibot page."""
        namespace = page.namespace()
        return {
            "site_hostname": page.site.hostname(),
            "page_id": page.pageid,
            "page_url": page.full_url(),
            "page_title": page.title(),
            "site_name": page.site.siteinfo["sitename"],
            "namespace_canonical": namespace.canonical_name,
            "namespace_localized": namespace.custom_name,
            "root_page": page.title(with_ns=False).split("/", 1)[0],
        }

    def _record_dashboard(self, page):
        """Record a dashboard in the registry, keyed on its stable page_id.

        Returns True if recorded, False if the write failed.
        """
        try:
            with DashboardRegistry() as registry:
                registry.record(**self._dashboard_metadata(page))
            return True
        except Exception as e:
            logger.warning("Failed to record dashboard %s: %s", page.title(), e)
            return False

    def warm_cache(self, limit=None):
        """Populate the Redis cache for all dashboard pages without running queries."""
        logger.info("Warming cache for pages on site %s", self.site.sitename)
        for page in self.get_all_pages(limit=limit):
            try:
                self.make_stats_object_arguments_for_page(page)
                logger.info("Cached config for %s", page.title())
            except (NoStartTemplateException, NoEndTemplateException, ConfigException):
                logger.warning("Skipping %s", page.title())
            except Exception as e:
                logger.warning("Error caching %s: %s", page.title(), e)

    def populate_registry(self, limit=None):
        """Record all dashboard pages in the registry without running queries."""
        logger.info("Populating registry for pages on site %s", self.site.sitename)
        count = 0
        skipped = 0
        for page in self.get_all_pages(limit=limit):
            try:
                self.make_stats_object_arguments_for_page(page)
            except NoStartTemplateException:
                logger.info("Skipping non-dashboard page %s", page.title())
                skipped += 1
                continue
            except Exception as e:
                logger.info("Recording misconfigured dashboard %s: %s", page.title(), e)
            if self._record_dashboard(page):
                count += 1
        logger.info(
            "Registered %d dashboards (skipped %d non-dashboards)", count, skipped
        )

    def process_all(self, limit=None):
        self.summary = "Weekly update of property usage stats"
        logger.info("Processing pages on site %s", self.site.sitename)
        for page in self.get_all_pages(limit=limit):
            logger.info("Processing page %s", page.title())
            try:
                self.process_page(page)
            except NoStartTemplateException:
                logger.warning("No start template on page %s, skipping", page.title())
            except NoEndTemplateException:
                logger.warning("No end template on page %s, skipping", page.title())
            except ConfigException:
                logger.warning("Bad configuration on page %s, skipping", page.title())
            except EmptyGroupingException:
                logger.warning(
                    "No groupings on page %s (selector/predicate matches nothing), "
                    "skipping",
                    page.title(),
                )
            except QueryException:
                logger.warning(
                    "A SPARQL query went wrong on page %s, skipping", page.title()
                )
            except UnsupportedGroupingConfigurationException:
                logger.warning(
                    "Unsupported grouping configuration on page %s, skipping",
                    page.title(),
                )
            except (
                pywikibot.exceptions.ApiTimeoutError,
                pywikibot.exceptions.ServerError,
            ) as e:
                logger.warning(
                    "Temporary server issue with page %s: %s. Will retry later.",
                    page.title(),
                    e,
                )
            except Exception as e:
                logger.error("Unknown error with page %s: %s", page.title(), e)

    def process_one_page(self, page_title):
        logger.info("Processing page %s", page_title)
        try:
            page = pywikibot.Page(self.site, page_title)
            return self.process_page(page, trigger_source="WEB")
        except (
            pywikibot.exceptions.ApiTimeoutError,
            pywikibot.exceptions.ServerError,
        ) as e:
            raise TransientServerException(
                f"Temporary server issue: {e}. Please try again later."
            ) from e

    def make_stats_object_for_page_title(self, page_title):
        key = self.make_cache_key(page_title)
        result = self.cache.get_cache_value(key)
        if not result:
            logger.info("No result in cache for %s, computing...", key)
            try:
                page = pywikibot.Page(self.site, page_title)
            except (
                pywikibot.exceptions.ApiTimeoutError,
                pywikibot.exceptions.ServerError,
            ) as e:
                raise TransientServerException(
                    f"Temporary server issue: {e}. Please try again later."
                ) from e
            result = self.make_stats_object_arguments_for_page(page)
        result.pop("grouping_link_mode", None)
        try:
            return PropertyStatistics(**result)
        except TypeError:
            raise ConfigException("The template parameters are incorrect.")
        except UnsupportedGroupingConfigurationException as e:
            raise ConfigException(e) from e


def args_parser():
    import argparse

    parser = argparse.ArgumentParser(description="Update Property dashboards on a wiki")
    parser.add_argument(
        "url",
        nargs="?",
        help="the URL of the wiki to update",
        default="https://www.wikidata.org/wiki/",
    )
    parser.add_argument(
        "--page",
        help="process a single page by title (instead of all pages)",
    )
    parser.add_argument(
        "--warm-cache-only",
        action="store_true",
        help="only populate the cache, don't run queries or update pages",
    )
    parser.add_argument(
        "--populate-registry",
        action="store_true",
        help="record all dashboard pages in the registry (no SPARQL queries)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="process at most N dashboards (applies to all batch modes)",
    )
    return parser.parse_args()


def main():
    """
    Main function. Bot does all the work.
    """
    logging.basicConfig(level=logging.INFO)
    args = args_parser()
    processor = PagesProcessor(url=args.url)
    if args.warm_cache_only:
        processor.warm_cache(limit=args.limit)
    elif args.populate_registry:
        processor.populate_registry(limit=args.limit)
    elif args.page:
        processor.process_one_page(args.page)
    else:
        processor.process_all(limit=args.limit)


if __name__ == "__main__":
    main()
