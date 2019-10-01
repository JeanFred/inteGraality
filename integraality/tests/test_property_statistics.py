# -*- coding: utf-8  -*-
"""Unit tests for functions.py."""

import unittest
from collections import OrderedDict

from property_statistics import PropertyStatistics


class PropertyStatisticsTest(unittest.TestCase):

    def setUp(self):
        properties = OrderedDict({
            'P21': None,
            'P19': None,
        })
        self.stats = PropertyStatistics(
            properties=properties,
            selector_sparql=u'wdt:P31 wd:Q41960',
            grouping_property=u'P551',
        )


class FormatHigherGroupingTextTest(PropertyStatisticsTest):

    def test_format_higher_grouping_text_default_qitem(self):
        result = self.stats.format_higher_grouping_text("Q1")
        expected = '| data-sort-value="Q1"| {{Q|Q1}}\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_string(self):
        self.stats.higher_grouping_type = "string"
        result = self.stats.format_higher_grouping_text("foo")
        expected = '| data-sort-value="foo"| foo\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_country(self):
        self.stats.higher_grouping_type = "country"
        result = self.stats.format_higher_grouping_text("AT")
        expected = '| data-sort-value="AT"| {{Flag|AT}}\n'
        self.assertEqual(result, expected)
