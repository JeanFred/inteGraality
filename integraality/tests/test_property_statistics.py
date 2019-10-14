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
        mock_get_totals_no_grouping.assert_called_once_with(self.stats)
        mock_get_property_info_no_grouping.assert_has_calls([
            call(self.stats, "P21"),
            call(self.stats, "P19"),
        ])


class MakeStatsForOneGroupingTest(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.stats.property_data = {
            'P21': OrderedDict([('Q3115846', 10), ('Q5087901', 6)]),
            'P19': OrderedDict([('Q3115846', 8), ('Q2166574', 5)]),
        }

    def test_make_stats_for_one_grouping(self):
        result = self.stats.make_stats_for_one_grouping("Q3115846", 10, None)
        expected = (
            '|-\n'
            '| {{Q|Q3115846}}\n'
            '| 10 \n'
            '| {{Coloured cell|100.0|10}}\n'
            '| {{Coloured cell|80.0|8}}\n'
        )
        self.assertEqual(result, expected)

    def test_make_stats_for_one_grouping_with_higher_grouping(self):
        self.stats.higher_grouping = "wdt:P17/wdt:P298"
        result = self.stats.make_stats_for_one_grouping("Q3115846", 10, "Q1")
        expected = (
            '|-\n'
            '| data-sort-value="Q1"| {{Q|Q1}}\n'
            '| {{Q|Q3115846}}\n'
            '| 10 \n'
            '| {{Coloured cell|100.0|10}}\n'
            '| {{Coloured cell|80.0|8}}\n'
        )
        self.assertEqual(result, expected)


class SparqlQueryTest(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        patcher = patch('pywikibot.data.sparql.SparqlQuery', autospec=True)
        self.mock_sparql_query = patcher.start()
        self.addCleanup(patcher.stop)

    def assert_query_called(self, query):
        self.mock_sparql_query.return_value.select.assert_called_once_with(query)


class GetCountFromSparqlTest(SparqlQueryTest):

    def test_return_count(self):
        self.mock_sparql_query.return_value.select.return_value = [{'count': '18'}]
        result = self.stats._get_count_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")
        self.assertEqual(result, 18)

    def test_return_None(self):
        self.mock_sparql_query.return_value.select.return_value = None
        result = self.stats._get_count_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")
        self.assertEqual(result, None)


class SparqlCountTest(SparqlQueryTest):

    def setUp(self):
        super().setUp()
        self.mock_sparql_query.return_value.select.return_value = [{'count': '18'}]

    def test_get_property_info_no_grouping(self):
        result = self.stats.get_property_info_no_grouping('P1')
        query = (
            "\n"
            "SELECT (COUNT(?entity) AS ?count) WHERE {\n"
            "    ?entity wdt:P31 wd:Q41960 .\n"
            "    MINUS { ?entity wdt:P551 _:b28. }\n"
            "    FILTER(EXISTS { ?entity p:P1 _:b29. })\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "ORDER BY DESC (?count)\n"
            "LIMIT 10\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, 18)
