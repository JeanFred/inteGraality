# -*- coding: utf-8  -*-
"""Unit tests for functions.py."""

import unittest
from collections import OrderedDict
from unittest.mock import call, patch

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


class MakeStatsForNoGroupTest(PropertyStatisticsTest):

    @patch('property_statistics.PropertyStatistics.get_property_info_no_grouping', autospec=True)
    @patch('property_statistics.PropertyStatistics.get_totals_no_grouping', autospec=True)
    def test_make_stats_for_no_group(self, mock_get_totals_no_grouping, mock_get_property_info_no_grouping):
        mock_get_totals_no_grouping.return_value = 20
        mock_get_property_info_no_grouping.side_effect = [2, 10]
        result = self.stats.make_stats_for_no_group()
        expected = "|-\n| No grouping \n| 20 \n| {{Coloured cell|10.0|2}}\n| {{Coloured cell|50.0|10}}\n"
        self.assertEqual(result, expected)
        mock_get_totals_no_grouping.assert_called_once()
        mock_get_property_info_no_grouping.assert_has_calls([
            call(self.stats, "P21"),
            call(self.stats, "P19"),
        ])
