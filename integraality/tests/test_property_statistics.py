# -*- coding: utf-8  -*-
"""Unit tests for functions.py."""

import unittest
from collections import OrderedDict
from unittest.mock import call, patch

from property_statistics import (
    PropertyConfig,
    PropertyStatistics,
    QueryException
)


class PropertyStatisticsTest(unittest.TestCase):

    def setUp(self):
        properties = [
            PropertyConfig(property='P21'),
            PropertyConfig(property='P19'),
        ]
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

    def setUp(self):
        super().setUp()
        patcher1 = patch('property_statistics.PropertyStatistics.get_totals_no_grouping', autospec=True)
        patcher2 = patch('property_statistics.PropertyStatistics.get_property_info_no_grouping', autospec=True)
        self.mock_get_totals_no_grouping = patcher1.start()
        self.mock_get_property_info_no_grouping = patcher2.start()
        self.addCleanup(patcher1.stop)
        self.addCleanup(patcher2.stop)

    def test_make_stats_for_no_group(self):
        self.mock_get_totals_no_grouping.return_value = 20
        self.mock_get_property_info_no_grouping.side_effect = [2, 10]
        result = self.stats.make_stats_for_no_group()
        expected = "|-\n| No grouping \n| 20 \n| {{Coloured cell|10.0|2}}\n| {{Coloured cell|50.0|10}}\n"
        self.assertEqual(result, expected)
        self.mock_get_totals_no_grouping.assert_called_once_with(self.stats)
        self.mock_get_property_info_no_grouping.assert_has_calls([
            call(self.stats, "P21"),
            call(self.stats, "P19"),
        ])

    def test_make_stats_for_no_group_with_higher_grouping(self):
        self.mock_get_totals_no_grouping.return_value = 20
        self.mock_get_property_info_no_grouping.side_effect = [2, 10]
        self.stats.higher_grouping = 'wdt:P17/wdt:P298'
        result = self.stats.make_stats_for_no_group()
        expected = "|-\n|\n| No grouping \n| 20 \n| {{Coloured cell|10.0|2}}\n| {{Coloured cell|50.0|10}}\n"
        self.assertEqual(result, expected)
        self.mock_get_totals_no_grouping.assert_called_once_with(self.stats)
        self.mock_get_property_info_no_grouping.assert_has_calls([
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

    @patch('pywikibot.ItemPage', autospec=True)
    def test_make_stats_for_one_grouping_with_grouping_link(self, mock_item_page):
        mock_item_page.return_value.labels = {'en': 'Bar'}
        self.stats.grouping_link = "Foo"
        result = self.stats.make_stats_for_one_grouping("Q3115846", 10, None)
        expected = (
            '|-\n'
            '| {{Q|Q3115846}}\n'
            '| [[Foo/Bar|10]] \n'
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

    def test_get_totals_for_property(self):
        result = self.stats.get_totals_for_property('P1')
        query = (
            "\n"
            "SELECT (COUNT(?item) as ?count) WHERE {\n"
            "  ?item wdt:P31 wd:Q41960\n"
            "  FILTER EXISTS { ?item p:P1[] } .\n"
            "}\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, 18)

    def test_get_totals_no_grouping(self):
        result = self.stats.get_totals_no_grouping()
        query = (
            "\n"
            "SELECT (COUNT(?item) as ?count) WHERE {\n"
            "  ?item wdt:P31 wd:Q41960\n"
            "  MINUS { ?item wdt:P551 _:b28. }\n"
            "}\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, 18)

    def test_get_totals(self):
        result = self.stats.get_totals()
        query = (
            "\n"
            "SELECT (COUNT(?item) as ?count) WHERE {\n"
            "  ?item wdt:P31 wd:Q41960\n"
            "}\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, 18)


class GetGroupingInformationTest(SparqlQueryTest):

    def test_get_grouping_information(self):
        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q3115846', 'count': '10'},
            {'grouping': 'http://www.wikidata.org/entity/Q5087901', 'count': '6'},
            {'grouping': 'http://www.wikidata.org/entity/Q623333', 'count': '6'}
        ]
        expected = (
            OrderedDict([('Q3115846', 10), ('Q5087901', 6), ('Q623333', 6)]),
            OrderedDict()
        )
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count > 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        result = self.stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_with_grouping_threshold(self):
        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q3115846', 'count': '10'},
            {'grouping': 'http://www.wikidata.org/entity/Q5087901', 'count': '6'},
            {'grouping': 'http://www.wikidata.org/entity/Q623333', 'count': '6'}
        ]
        expected = (
            OrderedDict([('Q3115846', 10), ('Q5087901', 6), ('Q623333', 6)]),
            OrderedDict()
        )
        self.stats.grouping_threshold = 5
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count > 5)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        result = self.stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_with_higher_grouping(self):
        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q3115846', 'higher_grouping': 'NZL', 'count': '10'},
            {'grouping': 'http://www.wikidata.org/entity/Q5087901', 'higher_grouping': 'USA', 'count': '6'},
            {'grouping': 'http://www.wikidata.org/entity/Q623333', 'higher_grouping': 'USA', 'count': '6'}
        ]
        expected = (
            OrderedDict([('Q3115846', 10), ('Q5087901', 6), ('Q623333', 6)]),
            OrderedDict([('Q3115846', 'NZL'), ('Q5087901', 'USA'), ('Q623333', 'USA')])
        )
        self.stats.higher_grouping = 'wdt:P17/wdt:P298'
        query = (
            "\n"
            "SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) "
            "(COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  OPTIONAL { ?grouping wdt:P17/wdt:P298 ?_higher_grouping }.\n"
            "} GROUP BY ?grouping ?higher_grouping\n"
            "HAVING (?count > 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        result = self.stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_empty_result(self):
        self.mock_sparql_query.return_value.select.return_value = None
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count > 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        with self.assertRaises(QueryException):
            self.stats.get_grouping_information()
        self.assert_query_called(query)


class GetPropertyInfoTest(SparqlQueryTest):

    def test_get_property_info(self):
        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q3115846', 'count': '10'},
            {'grouping': 'http://www.wikidata.org/entity/Q5087901', 'count': '6'},
            {'grouping': 'http://www.wikidata.org/entity/Q623333', 'count': '6'}
        ]
        expected = OrderedDict([('Q3115846', 10), ('Q5087901', 6), ('Q623333', 6)])

        result = self.stats.get_property_info('P1')
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  FILTER EXISTS { ?entity p:P1 [] } .\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count > 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_property_info_empty_result(self):
        self.mock_sparql_query.return_value.select.return_value = None
        expected = None
        result = self.stats.get_property_info('P1')
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  FILTER EXISTS { ?entity p:P1 [] } .\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count > 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, expected)
