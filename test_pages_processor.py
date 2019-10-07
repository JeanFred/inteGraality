# -*- coding: utf-8  -*-
"""Unit tests for functions.py."""

import unittest
from collections import OrderedDict

from pages_processor import ConfigException, PagesProcessor


class ProcessortTest(unittest.TestCase):

    def setUp(self):
        self.processor = PagesProcessor()


class Test(ProcessortTest):

    def setUp(self):
        self.text = """
Head
{{Property dashboard start
|properties=P136:genre,P404
|grouping_property=P400
|stats_for_no_group=1
|selector_sparql=wdt:P31/wdt:P279* wd:Q7889
|target_page_title=Wikidata:WikiProject Video games/Statistics/Platform
|grouping_link=Wikidata::WikiProject Video games/Reports/Platform
}}
foo
{{Property dashboard end}}
Bottom
"""
        self.final_text = """
Head
{{Property dashboard start
|properties=P136:genre,P404
|grouping_property=P400
|stats_for_no_group=1
|selector_sparql=wdt:P31/wdt:P279* wd:Q7889
|target_page_title=Wikidata:WikiProject Video games/Statistics/Platform
|grouping_link=Wikidata::WikiProject Video games/Reports/Platform
}}
bar
{{Property dashboard end}}
Bottom
"""

    def test(self):
        processor = PagesProcessor()
        result = processor.replace_in_page("bar", self.text)
        self.assertEqual(result, self.final_text)


class TestParseConfig(ProcessortTest):

    def setUp(self):
        self.processor = PagesProcessor()

    def test_normal_config(self):
        input_config = {
            'grouping_link': 'Wikidata:WikiProject Video games/Reports/Platform',
            'grouping_property': 'P400',
            'stats_for_no_group': '1',
            'properties': 'P136:genre,P404',
            'selector_sparql': 'wdt:P31/wdt:P279* wd:Q7889',
        }
        result = self.processor.parse_config(input_config)
        expected = {
            'grouping_link': 'Wikidata:WikiProject Video games/Reports/Platform',
            'grouping_property': 'P400',
            'stats_for_no_group': True,
            'properties': {'P136': 'genre', 'P404': None},
            'selector_sparql': 'wdt:P31/wdt:P279* wd:Q7889'
        }
        self.assertEqual(result, expected)

    def test_minimal_config(self):
        input_config = {
            'selector_sparql': 'wdt:P31/wdt:P279* wd:Q7889',
            'grouping_property': 'P400',
            'properties': 'P136:genre,P404',
        }
        result = self.processor.parse_config(input_config)
        expected = {
            'selector_sparql': 'wdt:P31/wdt:P279* wd:Q7889',
            'grouping_property': 'P400',
            'properties': {'P136': 'genre', 'P404': None},
            'stats_for_no_group': False,
        }
        self.assertEqual(result, expected)

    def test_full_config(self):
        input_config = {
            'grouping_link': 'Wikidata:WikiProject Video games/Reports/Platform',
            'grouping_property': 'P400',
            'stats_for_no_group': '1',
            'properties': 'P136:genre,P404',
            'selector_sparql': 'wdt:P31/wdt:P279* wd:Q7889',
            'grouping_threshold': '1',
            'property_threshold': '2',
        }
        result = self.processor.parse_config(input_config)
        expected = {
            'grouping_link': 'Wikidata:WikiProject Video games/Reports/Platform',
            'selector_sparql': 'wdt:P31/wdt:P279* wd:Q7889',
            'grouping_property': 'P400',
            'properties': {'P136': 'genre', 'P404': None},
            'stats_for_no_group': True,
            'grouping_threshold': '1',
            'property_threshold': '2',
        }
        self.assertEqual(result, expected)

    def test_empty_config(self):
        input_config = {}
        with(self.assertRaises(ConfigException)):
            self.processor.parse_config(input_config)

    def test_insufficient_config(self):
        input_config = {
            'selector_sparql': 'wdt:P31/wdt:P279* wd:Q7889',
        }
        with(self.assertRaises(ConfigException)):
            self.processor.parse_config(input_config)


class TestParseParams(ProcessortTest):

    def test_parse_config_from_params_minimal(self):
        params = ['grouping_property=P195', 'properties=P170:creator,P276', 'selector_sparql=wdt:P31 wd:Q3305213']
        expected = {
            'grouping_property': 'P195',
            'properties': 'P170:creator,P276',
            'selector_sparql': 'wdt:P31 wd:Q3305213'
        }
        result = self.processor.parse_config_from_params(params)
        self.assertEqual(result, expected)

    def test_parse_config_from_params_with_empty_param(self):
        params = ['', 'grouping_property=P195', 'properties=P170:creator,P276', 'selector_sparql=wdt:P31 wd:Q3305213']
        expected = {
            'grouping_property': 'P195',
            'properties': 'P170:creator,P276',
            'selector_sparql': 'wdt:P31 wd:Q3305213'
        }
        result = self.processor.parse_config_from_params(params)
        self.assertEqual(result, expected)


class TestParseConfigProperties(ProcessortTest):

    def test(self):
        properties = 'P136:genre,P404'
        result = self.processor.parse_config_properties(properties)
        self.assertEqual(result, {'P136': 'genre', 'P404': None})

    def test_with_trail_comma(self):
        properties = 'P136:genre,P404,'
        result = self.processor.parse_config_properties(properties)
        self.assertEqual(result, {'P136': 'genre', 'P404': None})

    def test_more_properties(self):
        properties = 'P136,P178,P123,P495,P577,P404,P437'
        result = self.processor.parse_config_properties(properties)
        expected = OrderedDict([
            ('P136', None),
            ('P178', None),
            ('P123', None),
            ('P495', None),
            ('P577', None),
            ('P404', None),
            ('P437', None),
        ])
        self.assertEqual(result, expected)
