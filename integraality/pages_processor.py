#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Bot to generate statistics

"""
import os
import re

from redis import StrictRedis
from ww import f

import pywikibot
from pywikibot import pagegenerators

from cache import RedisCache
from property_statistics import (
    DescriptionConfig,
    LabelConfig,
    PropertyConfig,
    PropertyStatistics,
    QueryException
)

REQUIRED_CONFIG_FIELDS = ['selector_sparql', 'grouping_property', 'properties']


class ProcessingException(Exception):
    pass


class ConfigException(ProcessingException):
    pass


class NoEndTemplateException(ProcessingException):
    pass


class NoStartTemplateException(ProcessingException):
    pass


class PagesProcessor:

    def __init__(self, url="https://www.wikidata.org/wiki/", cache_client=None):
        self.site = pywikibot.Site(url=url)
        self.template_name = 'Property dashboard'
        self.end_template_name = 'Property dashboard end'
        self.summary = u'Update property usage stats'

        self.outputs = []

        if not cache_client:
            host = os.getenv("REDIS_HOST", 'tools-redis.svc.eqiad.wmflabs')
            cache_client = StrictRedis(host=host, decode_responses=False)
        self.cache = RedisCache(cache_client=cache_client)

    def make_cache_key(self, page_title):
        return ":".join([self.site.code, page_title]).replace(" ", "_")

    def get_all_pages(self):
        template = pywikibot.Page(self.site, self.template_name, ns=10)
        return pagegenerators.ReferringPageGenerator(template, onlyTemplateInclusion=True)

    @staticmethod
    def extract_elements_from_template_param(template_param):
        """Extract and sanitize the contents of a parsed template param."""
        (field, _, value) = template_param.partition(u'=')
        return (field.strip(), value.replace('{{!}}', '|'))

    def parse_config_from_params(self, params):
        return {
            key: value for (key, value) in
            [self.extract_elements_from_template_param(param) for param in params]
            if key
        }

    def make_stats_object_arguments_for_page(self, page):
        all_templates_with_params = page.templatesWithParams()

        if self.template_name not in [template.title(with_ns=False) for (template, _) in all_templates_with_params]:
            msg = (
                "No start template '%s' found."
                "The likely explanation is that inteGraality was invoked from a page that transcludes the page with the template. "
                "Please invoke inteGraality directly from the page with the template." % self.template_name
            )
            raise NoStartTemplateException(msg)

        if self.end_template_name not in [template.title(with_ns=False) for (template, _) in all_templates_with_params]:
            raise NoEndTemplateException("No end template '%s' provided" % self.end_template_name)

        start_templates_with_params = [
            (template, params) for (template, params) in all_templates_with_params if
            template.title(with_ns=False) == self.template_name
        ]

        if len(start_templates_with_params) > 1:
            pywikibot.warn("More than one template on the page %s" % page.title())

        (template, params) = start_templates_with_params[0]
        parsed_config = self.parse_config_from_params(params)
        config = self.parse_config(parsed_config)
        key = self.make_cache_key(page.title())
        self.cache.set_cache_value(key, config)
        return config

    def make_stats_object_for_page(self, page):
        config = self.make_stats_object_arguments_for_page(page)
        try:
            return PropertyStatistics(**config)
        except TypeError:
            raise ConfigException("The template parameters are incorrect.")

    def process_page(self, page):
        self.cache.invalidate(self.make_cache_key(page.title()))
        stats = self.make_stats_object_for_page(page)
        try:
            output = stats.retrieve_and_process_data()
        except QueryException as e:
            raise ConfigException(e)
        new_text = self.replace_in_page(output, page.get())
        page.put(new_text, self.summary)

    def parse_config(self, config):
        for field in REQUIRED_CONFIG_FIELDS:
            if field not in config:
                pywikibot.output("Missing required field %s" % field)
                raise ConfigException("A required field is missing: %s" % field)
        config['columns'] = self.parse_config_properties(config['properties'])
        del config['properties']
        config['stats_for_no_group'] = bool(config.get('stats_for_no_group', False))
        return config

    @staticmethod
    def parse_config_properties(properties_string):
        properties = properties_string.split(',')
        properties_data = []
        for prop in properties:
            try:
                (key, title) = prop.split(':')
            except ValueError:
                (key, title) = (prop, None)
            if key:
                if key.startswith('P'):
                    splitted = key.split('/')
                    if len(splitted) == 3:
                        (property_name, value, qualifier) = splitted
                    elif len(splitted) == 2:
                        (property_name, value, qualifier) = (splitted[0], None, splitted[1])
                    else:
                        (property_name, value, qualifier) = (key, None, None)
                    entry = PropertyConfig(property=property_name, title=title, qualifier=qualifier, value=value)
                elif key.startswith('L'):
                    entry = LabelConfig(language=key[1:])
                elif key.startswith('D'):
                    entry = DescriptionConfig(language=key[1:])
                properties_data.append(entry)
        return properties_data

    def replace_in_page(self, output, page_text):
        regex_text = f('({{{{{self.template_name}.*?(?<!{{{{!)}}}}).*?({{{{{self.end_template_name}}}}})')
        regex = re.compile(regex_text, re.MULTILINE | re.DOTALL)
        new_text = re.sub(regex, r'\1\n%s\n\2' % output, page_text, count=1)
        return new_text

    def process_all(self):
        self.summary = u'Weekly update of property usage stats'
        pywikibot.output("Processing pages on site %s" % self.site.sitename)
        for page in self.get_all_pages():
            pywikibot.output("Processing page %s" % page.title())
            try:
                self.process_page(page)
            except NoStartTemplateException:
                pywikibot.output("No start template on page %s, skipping" % page.title())
            except NoEndTemplateException:
                pywikibot.output("No end template on page %s, skipping" % page.title())
            except ConfigException:
                pywikibot.output("Bad configuration on page %s, skipping" % page.title())
            except Exception as e:
                pywikibot.output("Unknown error with page %s: %s" % (page.title(), e))

    def process_one_page(self, page_title):
        page = pywikibot.Page(self.site, page_title)
        pywikibot.output("Processing page %s" % page.title())
        self.process_page(page)

    def make_stats_object_for_page_title(self, page_title):
        key = self.make_cache_key(page_title)
        result = self.cache.get_cache_value(key)
        if not result:
            print("No result in cache for %s, computing..." % key)
            page = pywikibot.Page(self.site, page_title)
            result = self.make_stats_object_arguments_for_page(page)
        try:
            return PropertyStatistics(**result)
        except TypeError:
            raise ConfigException("The template parameters are incorrect.")


def args_parser():
    import argparse
    parser = argparse.ArgumentParser(description='Update Property dashboards on a wiki')
    parser.add_argument("url",
                        nargs='?',
                        help="the URL of the wiki to update",
                        default="https://www.wikidata.org/wiki/",
                        )
    return parser.parse_args()


def main():
    """
    Main function. Bot does all the work.
    """
    args = args_parser()
    processor = PagesProcessor(url=args.url)
    processor.process_all()


if __name__ == "__main__":
    main()
