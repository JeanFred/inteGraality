# -*- coding: utf-8  -*-
"""Unit tests for functions.py."""

import argparse
import unittest
from unittest.mock import patch

import fakeredis

from integraality.pages_processor import ConfigException, PagesProcessor, main
from integraality.property_statistics import (
    DescriptionConfig,
    LabelConfig,
    PropertyConfig
)


class ProcessortTest(unittest.TestCase):

    def setUp(self):
        fake_cache_client = fakeredis.FakeStrictRedis()
        self.processor = PagesProcessor(cache_client=fake_cache_client)


class TestReplaceInPage(ProcessortTest):

    def setUp(self):
        self.processor = PagesProcessor()
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

    def test_replace_in_page(self):
        result = self.processor.replace_in_page("bar", self.text)
        self.assertEqual(result, self.final_text)

    def test_replace_in_page_escaped_pipe(self):
        text = self.text.replace('wd:Q7889', '{{!}}')
        final_text = self.final_text.replace('wd:Q7889', '{{!}}')
        result = self.processor.replace_in_page("bar", text)
        self.assertEqual(result, final_text)


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
            'columns': [
                PropertyConfig(property='P136', title='genre'),
                PropertyConfig(property='P404'),
            ],
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
            'columns': [
                PropertyConfig(property='P136', title='genre'),
                PropertyConfig(property='P404'),
            ],
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
            'columns': [
                PropertyConfig(property='P136', title='genre'),
                PropertyConfig(property='P404'),
            ],
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

    def test_parse_config_from_params_with_escaped_pipe(self):
        params = ['grouping_property=P195', 'properties=P170:creator,P276',
                  'selector_sparql=REGEX(?id, "^(a{{!}}b)")']
        expected = {
            'grouping_property': 'P195',
            'properties': 'P170:creator,P276',
            'selector_sparql': 'REGEX(?id, "^(a|b)")'
        }
        result = self.processor.parse_config_from_params(params)
        self.assertEqual(result, expected)


class TestParseConfigProperties(ProcessortTest):

    def test(self):
        properties = 'P136:genre,P404'
        result = self.processor.parse_config_properties(properties)
        expected = [
            PropertyConfig(property='P136', title='genre'),
            PropertyConfig(property='P404'),
        ]
        self.assertEqual(result, expected)

    def test_with_trail_comma(self):
        properties = 'P136:genre,P404,'
        result = self.processor.parse_config_properties(properties)
        expected = [
            PropertyConfig(property='P136', title='genre'),
            PropertyConfig(property='P404'),
        ]
        self.assertEqual(result, expected)

    def test_more_properties(self):
        properties = 'P136,P178,P123,P495,P577,P404,P437'
        result = self.processor.parse_config_properties(properties)
        expected = [
            PropertyConfig(property='P136'),
            PropertyConfig(property='P178'),
            PropertyConfig(property='P123'),
            PropertyConfig(property='P495'),
            PropertyConfig(property='P577'),
            PropertyConfig(property='P404'),
            PropertyConfig(property='P437'),
        ]
        self.assertEqual(result, expected)

    def test_with_qualifier(self):
        properties = 'P136:genre,P404,P669/P670'
        result = self.processor.parse_config_properties(properties)
        expected = [
            PropertyConfig(property='P136', title='genre'),
            PropertyConfig(property='P404'),
            PropertyConfig(property='P669', qualifier='P670'),
        ]
        self.assertEqual(result, expected)

    def test_with_qualifier_and_value(self):
        properties = 'P136:genre,P404,P553/Q17459/P670'
        result = self.processor.parse_config_properties(properties)
        expected = [
            PropertyConfig(property='P136', title='genre'),
            PropertyConfig(property='P404'),
            PropertyConfig(property='P553', value='Q17459', qualifier='P670')
        ]
        self.assertEqual(result, expected)

    def test_with_label(self):
        properties = 'P136:genre,Lbr,P553'
        result = self.processor.parse_config_properties(properties)
        expected = [
            PropertyConfig(property='P136', title='genre'),
            LabelConfig(language='br'),
            PropertyConfig(property='P553')
        ]
        self.assertEqual(result, expected)

    def test_with_description(self):
        properties = 'P136:genre,Lxy,P553'
        result = self.processor.parse_config_properties(properties)
        expected = [
            PropertyConfig(property='P136', title='genre'),
            DescriptionConfig(language='xy'),
            PropertyConfig(property='P553')
        ]
        self.assertEqual(result, expected)


class TestMain(unittest.TestCase):

    def setUp(self):
        patcher1 = patch('integraality.pages_processor.PagesProcessor', autospec=True)
        self.mock_pages_processor = patcher1.start()
        self.addCleanup(patcher1.stop)

        patcher2 = patch('argparse.ArgumentParser.parse_args', autospec=True)
        self.mock_args = patcher2.start()
        self.addCleanup(patcher2.stop)

    def test_main_url_argument(self):
        url = 'Foo'
        self.mock_args.return_value = argparse.Namespace(url=url)
        main()
        self.mock_pages_processor.assert_called_once_with(url)
        self.mock_pages_processor.return_value.process_all.assert_called_once_with()
