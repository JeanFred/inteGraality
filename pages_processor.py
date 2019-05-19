#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Bot to generate statistics

"""
import logging
import re

from ww import f

import pywikibot
from pywikibot import pagegenerators

from property_statistics import PropertyStatistics

REQUIRED_CONFIG_FIELDS = ['selector_sparql', 'grouping_property', 'properties']


class ConfigException(Exception):
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

    def process_page(self, page):
        page_text = page.get()
        all_templates_with_params = page.templatesWithParams()

        templates_with_params = [
            (template, params) for (template, params) in all_templates_with_params if
            template.title(with_ns=False) == self.template_name
        ]
        if len(templates_with_params) > 1:
            logging.warning("More than one template on the page")

        (template, params) = templates_with_params[0]
        config = {
            key: value for (key, value) in
            [self.extract_elements_from_template_param(param) for param in params]
        }
        config = self.parse_config(config)
        stats = PropertyStatistics(**config)
        output = stats.retrieve_and_process_data()
        new_text = self.replace_in_page(output, page_text)
        summary = u'Update property usage stats'
        page.put(new_text, summary)

    def parse_config(self, config):
        for field in REQUIRED_CONFIG_FIELDS:
            if field not in config:
                raise ConfigException
        config['properties'] = self.parse_config_properties(config['properties'])
        config['no_group_stats'] = bool(config.get('no_group_stats', False))
        return config

    @staticmethod
    def parse_config_properties(properties_string):
        properties = properties_string.split(',')
        properties_data = {}
        for prop in properties:
            try:
                (key, value) = prop.split(':')
            except ValueError:
                (key, value) = (prop, None)
            properties_data[key] = value
        return properties_data

    def replace_in_page(self, output, page_text):
        regex_text = f('({{{{{self.template_name}.*?}}}}).*?({{{{{self.end_template_name}}}}})')
        regex = re.compile(regex_text, re.MULTILINE | re.DOTALL)
        new_text = re.sub(regex, r'\1\n%s\n\2' % output, page_text, count=1)
        return new_text

    def process_all(self):
        for page in self.get_all_pages():
            logging.info(f('Processing {page.title()}'))
            self.process_page(page)

    def process_one_page(self, page_title):
        page = pywikibot.Page(self.repo, self.page_title)
        logging.info(f('Processing {page.title()}'))
        self.process_page(page)


def main(*args):
    """
    Main function. Bot does all the work.
    """
    processor = PagesProcessor()
    processor.process_all()


if __name__ == "__main__":
    main()
