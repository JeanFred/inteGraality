#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Bot to generate statistics

"""
import collections
import re

from ww import f

import pywikibot
from pywikibot import pagegenerators

from property_statistics import PropertyStatistics

REQUIRED_CONFIG_FIELDS = ['selector_sparql', 'grouping_property', 'properties']


class ProcessingException(Exception):
    pass


class ConfigException(ProcessingException):
    pass


class NoEndTemplateException(ProcessingException):
    pass


class PagesProcessor:

    def __init__(self):
        site = pywikibot.Site('en', 'wikipedia')
        self.repo = site.data_repository()
        self.template_name = 'Property dashboard'
        self.end_template_name = 'Property dashboard end'

        self.outputs = []

    def get_all_pages(self):
        template = pywikibot.Page(self.repo, self.template_name, ns=10)
        return pagegenerators.ReferringPageGenerator(template, onlyTemplateInclusion=True)

    @staticmethod
    def extract_elements_from_template_param(template_param):
        """Extract and sanitize the contents of a parsed template param."""
        (field, _, value) = template_param.partition(u'=')
        return (field.strip(), value)

    def parse_config_from_params(self, params):
        return {
            key: value for (key, value) in
            [self.extract_elements_from_template_param(param) for param in params]
            if key
        }

    def process_page(self, page):
        page_text = page.get()
        all_templates_with_params = page.templatesWithParams()

        if self.end_template_name not in [template.title(with_ns=False) for (template, _) in all_templates_with_params]:
            raise NoEndTemplateException()

        start_templates_with_params = [
            (template, params) for (template, params) in all_templates_with_params if
            template.title(with_ns=False) == self.template_name
        ]
        if len(start_templates_with_params) > 1:
            pywikibot.warn("More than one template on the page %s" % page.title())

        (template, params) = start_templates_with_params[0]
        parsed_config = self.parse_config_from_params(params)
        config = self.parse_config(parsed_config)
        stats = PropertyStatistics(**config)
        output = stats.retrieve_and_process_data()
        new_text = self.replace_in_page(output, page_text)
        summary = u'Update property usage stats'
        page.put(new_text, summary)

    def parse_config(self, config):
        for field in REQUIRED_CONFIG_FIELDS:
            if field not in config:
                pywikibot.output("Missing required field %s" % field)
                raise ConfigException
        config['properties'] = self.parse_config_properties(config['properties'])
        config['stats_for_no_group'] = bool(config.get('stats_for_no_group', False))
        return config

    @staticmethod
    def parse_config_properties(properties_string):
        properties = properties_string.split(',')
        properties_data = collections.OrderedDict()
        for prop in properties:
            try:
                (key, value) = prop.split(':')
            except ValueError:
                (key, value) = (prop, None)
            if key:
                properties_data[key] = value
        return properties_data

    def replace_in_page(self, output, page_text):
        regex_text = f('({{{{{self.template_name}.*?}}}}).*?({{{{{self.end_template_name}}}}})')
        regex = re.compile(regex_text, re.MULTILINE | re.DOTALL)
        new_text = re.sub(regex, r'\1\n%s\n\2' % output, page_text, count=1)
        return new_text

    def process_all(self):
        for page in self.get_all_pages():
            pywikibot.output("Processing page %s" % page.title())
            try:
                self.process_page(page)
            except NoEndTemplateException as e:
                pywikibot.output("No end template on page %s, skipping" % page.title())
            except ConfigException as e:
                pywikibot.output("Bad configuration on page %s, skipping" % page.title())

    def process_one_page(self, page_title):
        page = pywikibot.Page(self.repo, page_title)
        pywikibot.output("Processing page %s" % page.title())
        self.process_page(page)


def main(*args):
    """
    Main function. Bot does all the work.
    """
    processor = PagesProcessor()
    processor.process_all()


if __name__ == "__main__":
    main()
