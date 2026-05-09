#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Bot to generate statistics

"""

import logging
import os
import re
from time import perf_counter

import pywikibot
from redis import StrictRedis

from .cache import RedisCache
from .config_assembler import ConfigAssembler, ConfigAssemblyException
from .grouping import UnsupportedGroupingConfigurationException
from .grouping_page_creator import GroupingPageCreator
from .page_saving import save_to_wiki_or_local
from .property_statistics import PropertyStatistics
from .sparql_utils import QueryException

logger = logging.getLogger("integraality.update")


class ProcessingException(Exception):
    pass


class ConfigException(ProcessingException):
    pass


class NoEndTemplateException(ProcessingException):
    pass


class NoStartTemplateException(ProcessingException):
    pass


class TransientServerException(Exception):
    """Exception for temporary server issues that may resolve on retry."""

    pass


class PagesProcessor:
    def __init__(self, url="https://www.wikidata.org/wiki/", cache_client=None):
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

        return urlparse(url).netloc

    def make_cache_key(self, page_title):
        return ":".join([self._site_code_from_url(self.url), page_title]).replace(
            " ", "_"
        )

    def get_all_pages(self):
        template = pywikibot.Page(self.site, self.template_name, ns=10)
        return template.getReferences(only_template_inclusion=True)

    def make_stats_object_arguments_for_page(self, page):
        all_templates_with_params = page.templatesWithParams()

        if self.template_name not in [
            template.title(with_ns=False) for (template, _) in all_templates_with_params
        ]:
            msg = (
                "No start template '%s' found."
                "The likely explanation is that inteGraality was invoked from a page that transcludes the page with the template. "
                "Please invoke inteGraality directly from the page with the template."
                % self.template_name
            )
            raise NoStartTemplateException(msg)

        if self.end_template_name not in [
            template.title(with_ns=False) for (template, _) in all_templates_with_params
        ]:
            raise NoEndTemplateException(
                "No end template '%s' provided" % self.end_template_name
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

    def process_page(self, page):
        start_time = perf_counter()
        logger.debug("Invalidating cache key for %s", page.title())
        self.cache.invalidate(self.make_cache_key(page.title()))
        logger.info("Parsing page configuration...")
        stats, grouping_link_mode = self.make_stats_object_for_page(page)
        groupings = stats.retrieve_data()
        output = stats.process_data(groupings)
        elapsed_time = perf_counter() - start_time
        new_text = self.replace_in_page(output, page.get())
        summary = (
            self.summary
            + f" using {stats.get_sparql_engine_name()} ({int(elapsed_time)}s)"
        )
        logger.info("Saving to wiki...")
        save_to_wiki_or_local(page, summary, new_text)

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

    def replace_in_page(self, output, page_text):
        regex_text = f"({{{{{self.template_name}.*?(?<!{{{{!)}}}}).*?({{{{{self.end_template_name}}}}})"
        regex = re.compile(regex_text, re.MULTILINE | re.DOTALL)
        new_text = re.sub(regex, r"\1\n%s\n\2" % output, page_text, count=1)
        return new_text

    def warm_cache(self):
        """Populate the Redis cache for all dashboard pages without running queries."""
        logger.info("Warming cache for pages on site %s", self.site.sitename)
        for page in self.get_all_pages():
            try:
                self.make_stats_object_arguments_for_page(page)
                logger.info("Cached config for %s", page.title())
            except (NoStartTemplateException, NoEndTemplateException, ConfigException):
                logger.warning("Skipping %s", page.title())
            except Exception as e:
                logger.warning("Error caching %s: %s", page.title(), e)

    def process_all(self):
        self.summary = "Weekly update of property usage stats"
        logger.info("Processing pages on site %s", self.site.sitename)
        for page in self.get_all_pages():
            logger.info("Processing page %s", page.title())
            try:
                self.process_page(page)
            except NoStartTemplateException:
                logger.warning("No start template on page %s, skipping", page.title())
            except NoEndTemplateException:
                logger.warning("No end template on page %s, skipping", page.title())
            except ConfigException:
                logger.warning("Bad configuration on page %s, skipping", page.title())
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
                pywikibot.exceptions.TimeoutError,
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
        page = pywikibot.Page(self.site, page_title)
        logger.info("Processing page %s", page.title())
        try:
            return self.process_page(page)
        except (
            pywikibot.exceptions.TimeoutError,
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
            page = pywikibot.Page(self.site, page_title)
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
        "--warm-cache-only",
        action="store_true",
        help="only populate the cache, don't run queries or update pages",
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
        processor.warm_cache()
    else:
        processor.process_all()


if __name__ == "__main__":
    main()
