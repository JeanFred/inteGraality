# -*- coding: utf-8  -*-
"""Unit tests for pages_processor.py."""

import argparse
import unittest
from unittest.mock import patch

import fakeredis

from ..pages_processor import PagesProcessor, main


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
        text = self.text.replace("wd:Q7889", "{{!}}")
        final_text = self.final_text.replace("wd:Q7889", "{{!}}")
        result = self.processor.replace_in_page("bar", text)
        self.assertEqual(result, final_text)


class TestMain(unittest.TestCase):
    def setUp(self):
        patcher1 = patch("integraality.pages_processor.PagesProcessor", autospec=True)
        self.mock_pages_processor = patcher1.start()
        self.addCleanup(patcher1.stop)

        patcher2 = patch("argparse.ArgumentParser.parse_args", autospec=True)
        self.mock_args = patcher2.start()
        self.addCleanup(patcher2.stop)

    def test_main_url_argument(self):
        url = "Foo"
        self.mock_args.return_value = argparse.Namespace(url=url, warm_cache_only=False)
        main()
        self.mock_pages_processor.assert_called_once_with(url)
        self.mock_pages_processor.return_value.process_all.assert_called_once_with()
