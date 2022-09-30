# -*- coding: utf-8  -*-
"""Unit tests for functions.py."""

import unittest
from collections import OrderedDict
from unittest.mock import patch

import pywikibot

from column import DescriptionColumn, LabelColumn, PropertyColumn
from line import PropertyGrouping, UnknownValueGrouping, YearGrouping
from property_statistics import PropertyStatistics, QueryException


class PropertyStatisticsTest(unittest.TestCase):

    def setUp(self):
        self.columns = [
            PropertyColumn(property='P21'),
            PropertyColumn(property='P19'),
            PropertyColumn(property='P1', qualifier='P2'),
            PropertyColumn(property='P3', value='Q4', qualifier='P5'),
            LabelColumn(language='br'),
            DescriptionColumn(language='xy'),
        ]
        self.stats = PropertyStatistics(
            columns=self.columns,
            selector_sparql=u'wdt:P31 wd:Q41960',
            grouping_property=u'P551',
            property_threshold=10
        )


class SparqlQueryTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        patcher = patch('pywikibot.data.sparql.SparqlQuery', autospec=True)
        self.mock_sparql_query = patcher.start()
        self.addCleanup(patcher.stop)

    def assert_query_called(self, query):
        self.mock_sparql_query.return_value.select.assert_called_once_with(query)


class TestLabelColumn(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.column = LabelColumn('br')

    def test_simple(self):
        result = self.column.make_column_header()
        expected = u'! data-sort-type="number"|{{#language:br}}\n'
        self.assertEqual(result, expected)

    def test_get_key(self):
        result = self.column.get_key()
        self.assertEqual(result, 'Lbr')

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        query = (
            "\n"
            "SELECT (COUNT(*) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960\n"
            "  FILTER(EXISTS {\n"
            "    ?entity rdfs:label ?lang_label.\n"
            "    FILTER((LANG(?lang_label)) = 'br').\n"
            "  })\n"
            "}\n"
        )
        self.assertEqual(result, query)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  FILTER(EXISTS {\n"
            "    ?entity rdfs:label ?lang_label.\n"
            "    FILTER((LANG(?lang_label)) = 'br').\n"
            "  })\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count >= 10)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assertEqual(result, query)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        query = (
            "\n"
            "SELECT (COUNT(*) AS ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  MINUS { ?entity wdt:P551 _:b28. }\n"
            "  FILTER(EXISTS {\n"
            "    ?entity rdfs:label ?lang_label.\n"
            "    FILTER((LANG(?lang_label)) = 'br').\n"
            "  })\n"
            "}\n"
        )
        self.assertEqual(result, query)


class TestDescriptionColumn(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.column = DescriptionColumn('br')

    def test_simple(self):
        result = self.column.make_column_header()
        expected = u'! data-sort-type="number"|{{#language:br}}\n'
        self.assertEqual(result, expected)

    def test_get_key(self):
        result = self.column.get_key()
        self.assertEqual(result, 'Dbr')

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        query = (
            "\n"
            "SELECT (COUNT(*) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960\n"
            "  FILTER(EXISTS {\n"
            "    ?entity schema:description ?lang_label.\n"
            "    FILTER((LANG(?lang_label)) = 'br').\n"
            "  })\n"
            "}\n"
        )
        self.assertEqual(result, query)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  FILTER(EXISTS {\n"
            "    ?entity schema:description ?lang_label.\n"
            "    FILTER((LANG(?lang_label)) = 'br').\n"
            "  })\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count >= 10)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assertEqual(result, query)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        query = (
            "\n"
            "SELECT (COUNT(*) AS ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  MINUS { ?entity wdt:P551 _:b28. }\n"
            "  FILTER(EXISTS {\n"
            "    ?entity schema:description ?lang_label.\n"
            "    FILTER((LANG(?lang_label)) = 'br').\n"
            "  })\n"
            "}\n"
        )

        self.assertEqual(result, query)


class MakeStatsForNoGroupTest(SparqlQueryTest, PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        patcher1 = patch('property_statistics.PropertyStatistics.get_totals_no_grouping', autospec=True)
        self.mock_get_totals_no_grouping = patcher1.start()
        self.addCleanup(patcher1.stop)
        self.mock_get_totals_no_grouping.return_value = 20
        self.mock_sparql_query.return_value.select.side_effect = [
            [{'count': '2'}],
            [{'count': '10'}],
            [{'count': '15'}],
            [{'count': '5'}],
            [{'count': '4'}],
            [{'count': '8'}],
        ]

    def test_make_stats_for_no_group(self):
        result = self.stats.make_stats_for_no_group()
        expected = (
            "|-\n"
            "| No grouping\n"
            "| 20 \n"
            "| {{Integraality cell|10.0|2|column=P21|grouping=None}}\n"
            "| {{Integraality cell|50.0|10|column=P19|grouping=None}}\n"
            "| {{Integraality cell|75.0|15|column=P1/P2|grouping=None}}\n"
            "| {{Integraality cell|25.0|5|column=P3/Q4/P5|grouping=None}}\n"
            "| {{Integraality cell|20.0|4|column=Lbr|grouping=None}}\n"
            "| {{Integraality cell|40.0|8|column=Dxy|grouping=None}}\n"
        )
        self.assertEqual(result, expected)
        self.mock_get_totals_no_grouping.assert_called_once_with(self.stats)
        self.assertEqual(self.mock_sparql_query.call_count, 6)

    def test_make_stats_for_no_group_with_higher_grouping(self):
        self.stats.higher_grouping = 'wdt:P17/wdt:P298'
        result = self.stats.make_stats_for_no_group()
        expected = (
            "|-\n"
            "|\n"
            "| No grouping\n"
            "| 20 \n"
            "| {{Integraality cell|10.0|2|column=P21|grouping=None}}\n"
            "| {{Integraality cell|50.0|10|column=P19|grouping=None}}\n"
            "| {{Integraality cell|75.0|15|column=P1/P2|grouping=None}}\n"
            "| {{Integraality cell|25.0|5|column=P3/Q4/P5|grouping=None}}\n"
            "| {{Integraality cell|20.0|4|column=Lbr|grouping=None}}\n"
            "| {{Integraality cell|40.0|8|column=Dxy|grouping=None}}\n"
        )
        self.assertEqual(result, expected)
        self.mock_get_totals_no_grouping.assert_called_once_with(self.stats)
        self.assertEqual(self.mock_sparql_query.call_count, 6)


class MakeStatsForOneGroupingTest(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        # self.stats.column_data = {
        #     'P21': OrderedDict([
        #         ('Q3115846', 10), ('Q5087901', 6),
        #         ('UNKNOWN_VALUE', 4)
        #     ]),
        #     'P19': OrderedDict([('Q3115846', 8), ('Q2166574', 5)]),
        #     'P1P2': OrderedDict([('Q3115846', 2), ('Q2166574', 9)]),
        #     'P3Q4P5': OrderedDict([('Q3115846', 7), ('Q2166574', 1)]),
        #     'Lbr': OrderedDict([('Q3115846', 1), ('Q2166574', 2)]),
        #     'Dxy': OrderedDict([('Q3115846', 2), ('Q2166574', 1)]),
        # }

    def test_format_stats_for_one_grouping(self):
        grouping = PropertyGrouping(title='Q3115846', count=10)
        grouping.cells = OrderedDict([
            ('P21', 10),
            ('P19', 8),
            ('P1P2', 2),
            ('P3Q4P5', 7),
            ('Lbr', 1),
            ('Dxy', 2),
        ])
        result = self.stats.format_stats_for_one_grouping(grouping)
        expected = (
            '|-\n'
            '| {{Q|Q3115846}}\n'
            '| 10 \n'
            '| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n'
            '| {{Integraality cell|80.0|8|column=P19|grouping=Q3115846}}\n'
            '| {{Integraality cell|20.0|2|column=P1/P2|grouping=Q3115846}}\n'
            '| {{Integraality cell|70.0|7|column=P3/Q4/P5|grouping=Q3115846}}\n'
            '| {{Integraality cell|10.0|1|column=Lbr|grouping=Q3115846}}\n'
            '| {{Integraality cell|20.0|2|column=Dxy|grouping=Q3115846}}\n'
        )
        self.assertEqual(result, expected)

    def test_make_stats_for_unknown_grouping(self):
        grouping = UnknownValueGrouping(title='UNKNOWN_VALUE', count=10)
        grouping.cells = OrderedDict([
            ('P21', 4),
        ])
        result = self.stats.format_stats_for_one_grouping(grouping)
        expected = (
            '|-\n'
            '| {{int:wikibase-snakview-variations-somevalue-label}}\n'
            '| 10 \n'
            '| {{Integraality cell|40.0|4|column=P21|grouping=UNKNOWN_VALUE}}\n'
            '| {{Integraality cell|0|0|column=P19|grouping=UNKNOWN_VALUE}}\n'
            '| {{Integraality cell|0|0|column=P1/P2|grouping=UNKNOWN_VALUE}}\n'
            '| {{Integraality cell|0|0|column=P3/Q4/P5|grouping=UNKNOWN_VALUE}}\n'
            '| {{Integraality cell|0|0|column=Lbr|grouping=UNKNOWN_VALUE}}\n'
            '| {{Integraality cell|0|0|column=Dxy|grouping=UNKNOWN_VALUE}}\n'
        )
        self.assertEqual(result, expected)

    def test_format_stats_for_one_grouping_with_higher_grouping(self):
        self.stats.higher_grouping = "wdt:P17/wdt:P298"
        grouping = PropertyGrouping(title='Q3115846', count=10, higher_grouping="Q1")
        grouping.cells = OrderedDict([
            ('P21', 10),
            ('P19', 8),
            ('P1P2', 2),
            ('P3Q4P5', 7),
            ('Lbr', 1),
            ('Dxy', 2),
        ])
        result = self.stats.format_stats_for_one_grouping(grouping)
        expected = (
            '|-\n'
            '| data-sort-value="Q1"| {{Q|Q1}}\n'
            '| {{Q|Q3115846}}\n'
            '| 10 \n'
            '| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n'
            '| {{Integraality cell|80.0|8|column=P19|grouping=Q3115846}}\n'
            '| {{Integraality cell|20.0|2|column=P1/P2|grouping=Q3115846}}\n'
            '| {{Integraality cell|70.0|7|column=P3/Q4/P5|grouping=Q3115846}}\n'
            '| {{Integraality cell|10.0|1|column=Lbr|grouping=Q3115846}}\n'
            '| {{Integraality cell|20.0|2|column=Dxy|grouping=Q3115846}}\n'
        )
        self.assertEqual(result, expected)

    @patch('pywikibot.ItemPage', autospec=True)
    def test_format_stats_for_one_grouping_with_grouping_link(self, mock_item_page):
        mock_item_page.return_value.labels = {'en': 'Bar'}
        self.stats.grouping_link = "Foo"
        grouping = PropertyGrouping(title='Q3115846', count=10)
        grouping.cells = OrderedDict([
            ('P21', 10),
            ('P19', 8),
            ('P1P2', 2),
            ('P3Q4P5', 7),
            ('Lbr', 1),
            ('Dxy', 2),
        ])
        result = self.stats.format_stats_for_one_grouping(grouping)
        expected = (
            '|-\n'
            '| {{Q|Q3115846}}\n'
            '| [[Foo/Bar|10]] \n'
            '| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n'
            '| {{Integraality cell|80.0|8|column=P19|grouping=Q3115846}}\n'
            '| {{Integraality cell|20.0|2|column=P1/P2|grouping=Q3115846}}\n'
            '| {{Integraality cell|70.0|7|column=P3/Q4/P5|grouping=Q3115846}}\n'
            '| {{Integraality cell|10.0|1|column=Lbr|grouping=Q3115846}}\n'
            '| {{Integraality cell|20.0|2|column=Dxy|grouping=Q3115846}}\n'
        )
        self.assertEqual(result, expected)

    @patch('pywikibot.ItemPage', autospec=True)
    def test_format_stats_for_one_grouping_with_grouping_link_failure(self, mock_item_page):
        mock_item_page.side_effect = pywikibot.exceptions.InvalidTitleError('Error')
        self.stats.grouping_link = "Foo"
        grouping = PropertyGrouping(title='Q3115846', count=10)
        grouping.cells = OrderedDict([
            ('P21', 10),
            ('P19', 8),
            ('P1P2', 2),
            ('P3Q4P5', 7),
            ('Lbr', 1),
            ('Dxy', 2),
        ])
        with self.assertLogs(level='INFO') as cm:
            result = self.stats.format_stats_for_one_grouping(grouping)
        expected = (
            '|-\n'
            '| {{Q|Q3115846}}\n'
            '| [[Foo/Q3115846|10]] \n'
            '| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n'
            '| {{Integraality cell|80.0|8|column=P19|grouping=Q3115846}}\n'
            '| {{Integraality cell|20.0|2|column=P1/P2|grouping=Q3115846}}\n'
            '| {{Integraality cell|70.0|7|column=P3/Q4/P5|grouping=Q3115846}}\n'
            '| {{Integraality cell|10.0|1|column=Lbr|grouping=Q3115846}}\n'
            '| {{Integraality cell|20.0|2|column=Dxy|grouping=Q3115846}}\n'
        )
        self.assertEqual(result, expected)
        self.assertEqual(cm.output, ['INFO:root:Could not retrieve label for Q3115846'])


class GetQueryForItemsForPropertyPositive(PropertyStatisticsTest):

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(self.stats.columns.get('P21'), 'Q3115846')
        expected = """
SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 wd:Q3115846 .
  ?entity p:P21 ?prop . OPTIONAL { ?prop ps:P21 ?value }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_no_grouping(self):
        result = self.stats.get_query_for_items_for_property_positive(self.stats.columns.get('P21'), self.stats.GROUP_MAPPING.NO_GROUPING)
        expected = """
SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  MINUS {
    ?entity wdt:P551 [] .
  }
  ?entity p:P21 ?prop . OPTIONAL { ?prop ps:P21 ?value }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_totals(self):
        result = self.stats.get_query_for_items_for_property_positive(self.stats.columns.get('P21'), self.stats.GROUP_MAPPING.TOTALS)
        expected = """
SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity p:P21 ?prop . OPTIONAL { ?prop ps:P21 ?value }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_label(self):
        result = self.stats.get_query_for_items_for_property_positive(self.stats.columns.get('Lbr'), 'Q3115846')
        expected = """
SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 wd:Q3115846 .
  FILTER(EXISTS {
    ?entity rdfs:label ?lang_label.
    FILTER((LANG(?lang_label)) = "br").
  })
  SERVICE wikibase:label { bd:serviceParam wikibase:language "br". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_unknown_value_grouping(self):
        result = self.stats.get_query_for_items_for_property_positive(self.stats.columns.get('P21'), self.stats.GROUP_MAPPING.UNKNOWN_VALUE)
        expected = """
SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 ?grouping.
  FILTER wikibase:isSomeValue(?grouping).
  ?entity p:P21 ?prop . OPTIONAL { ?prop ps:P21 ?value }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_year_grouping(self):
        stats = PropertyStatistics(
            columns=self.columns,
            selector_sparql=u'wdt:P31 wd:Q41960',
            grouping_property=u'P577',
            grouping_type='year',
            property_threshold=10
        )
        result = stats.get_query_for_items_for_property_positive(self.stats.columns.get('P21'), 2006)
        expected = """
SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P577 ?date.
  BIND(YEAR(?date) as ?year).
  FILTER(?year = 2006).
  ?entity p:P21 ?prop . OPTIONAL { ?prop ps:P21 ?value }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)


class GetQueryForItemsForPropertyNegative(PropertyStatisticsTest):

    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative(self.stats.columns.get('P21'), 'Q3115846')
        expected = """
SELECT DISTINCT ?entity ?entityLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 wd:Q3115846 .
  MINUS {
    {?entity a wdno:P21 .} UNION
    {?entity wdt:P21 ?prop .}
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_no_grouping(self):
        result = self.stats.get_query_for_items_for_property_negative(self.stats.columns.get('P21'), self.stats.GROUP_MAPPING.NO_GROUPING)
        expected = """
SELECT DISTINCT ?entity ?entityLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  MINUS {
    {?entity wdt:P551 [] .} UNION
    {?entity a wdno:P21 .} UNION
    {?entity wdt:P21 ?prop .}
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_totals(self):
        result = self.stats.get_query_for_items_for_property_negative(self.stats.columns.get('P21'), self.stats.GROUP_MAPPING.TOTALS)
        expected = """
SELECT DISTINCT ?entity ?entityLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  MINUS {
    {?entity a wdno:P21 .} UNION
    {?entity wdt:P21 ?prop .}
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_label(self):
        result = self.stats.get_query_for_items_for_property_negative(self.stats.columns.get('Lbr'), 'Q3115846')
        expected = """
SELECT DISTINCT ?entity ?entityLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 wd:Q3115846 .
  MINUS {
    { ?entity rdfs:label ?lang_label.
    FILTER((LANG(?lang_label)) = "br") }
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_unknown_value_grouping(self):
        result = self.stats.get_query_for_items_for_property_negative(self.stats.columns.get('P21'), self.stats.GROUP_MAPPING.UNKNOWN_VALUE)
        expected = """
SELECT DISTINCT ?entity ?entityLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 ?grouping.
  FILTER wikibase:isSomeValue(?grouping).
  MINUS {
    {?entity a wdno:P21 .} UNION
    {?entity wdt:P21 ?prop .}
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_year_grouping(self):
        stats = PropertyStatistics(
            columns=self.columns,
            selector_sparql=u'wdt:P31 wd:Q41960',
            grouping_property=u'P577',
            grouping_type='year',
            property_threshold=10
        )
        result = stats.get_query_for_items_for_property_negative(self.stats.columns.get('P21'), 2006)
        expected = """
SELECT DISTINCT ?entity ?entityLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P577 ?date.
  BIND(YEAR(?date) as ?year).
  FILTER(?year = 2006).
  MINUS {
    {?entity a wdno:P21 .} UNION
    {?entity wdt:P21 ?prop .}
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)


class GetCountFromSparqlTest(SparqlQueryTest, PropertyStatisticsTest):

    def test_return_count(self):
        self.mock_sparql_query.return_value.select.return_value = [{'count': '18'}]
        result = self.stats._get_count_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")
        self.assertEqual(result, 18)

    def test_return_None(self):
        self.mock_sparql_query.return_value.select.return_value = None
        with self.assertRaises(QueryException):
            self.stats._get_count_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")


class GetGroupingCountsFromSparqlTest(SparqlQueryTest, PropertyStatisticsTest):

    def test_return_count(self):
        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q1', 'count': 10},
            {'grouping': 'http://www.wikidata.org/entity/Q2', 'count': 5},
        ]
        result = self.stats._get_grouping_counts_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")
        expected = OrderedDict([('Q1', 10), ('Q2', 5)])
        self.assertEqual(result, expected)

    def test_return_None(self):
        self.mock_sparql_query.return_value.select.return_value = None
        result = self.stats._get_grouping_counts_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")
        self.assertEqual(result, None)

    def test_return_count_with_unknown(self):
        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q1', 'count': 10},
            {'grouping': 'http://www.wikidata.org/entity/Q2', 'count': 5},
            {'grouping': 'http://www.wikidata.org/.well-known/genid/6ab4c2d7cb4ac72721335af5b8ba09c7', 'count': 2},
            {'grouping': 'http://www.wikidata.org/.well-known/genid/1469448a291c6fbe5df8306cb52ef18b', 'count': 1}

        ]
        result = self.stats._get_grouping_counts_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")
        expected = OrderedDict([('Q1', 10), ('Q2', 5), ('UNKNOWN_VALUE', 3)])
        self.assertEqual(result, expected)


class SparqlCountTest(SparqlQueryTest, PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.mock_sparql_query.return_value.select.return_value = [{'count': '18'}]

    def test_get_totals_no_grouping(self):
        result = self.stats.get_totals_no_grouping()
        query = (
            "\n"
            "SELECT (COUNT(*) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960\n"
            "  MINUS { ?entity wdt:P551 _:b28. }\n"
            "}\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, 18)

    def test_get_totals(self):
        result = self.stats.get_totals()
        query = (
            "\n"
            "SELECT (COUNT(*) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960\n"
            "}\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, 18)


class GetGroupingInformationTest(SparqlQueryTest, PropertyStatisticsTest):

    def test_get_grouping_information(self):
        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q3115846', 'count': '10'},
            {'grouping': 'http://www.wikidata.org/entity/Q5087901', 'count': '6'},
            {'grouping': 'http://www.wikidata.org/entity/Q623333', 'count': '6'}
        ]
        expected = {
            'Q3115846': PropertyGrouping(title='Q3115846', count=10),
            'Q5087901': PropertyGrouping(title='Q5087901', count=6),
            'Q623333': PropertyGrouping(title='Q623333', count=6)
        }
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count >= 20)\n"
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
        expected = {
            'Q3115846': PropertyGrouping(title='Q3115846', count=10),
            'Q5087901': PropertyGrouping(title='Q5087901', count=6),
            'Q623333': PropertyGrouping(title='Q623333', count=6)
        }
        self.stats.grouping_threshold = 5
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count >= 5)\n"
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
        expected = {
            'Q3115846': PropertyGrouping(title='Q3115846', count=10, higher_grouping='NZL'),
            'Q5087901': PropertyGrouping(title='Q5087901', count=6, higher_grouping='USA'),
            'Q623333': PropertyGrouping(title='Q623333', count=6, higher_grouping='USA')
        }
        self.stats.higher_grouping = 'wdt:P17/wdt:P298'
        query = (
            "\n"
            "SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) "
            "(COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  OPTIONAL { ?grouping wdt:P17/wdt:P298 ?_higher_grouping }.\n"
            "} GROUP BY ?grouping ?higher_grouping\n"
            "HAVING (?count >= 20)\n"
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
            "HAVING (?count >= 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        with self.assertRaises(QueryException):
            self.stats.get_grouping_information()
        self.assert_query_called(query)

    def test_get_grouping_information_timeout(self):
        self.mock_sparql_query.return_value.select.side_effect = pywikibot.exceptions.TimeoutError("Error")
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count >= 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        with self.assertRaises(QueryException):
            self.stats.get_grouping_information()
        self.assert_query_called(query)

    def test_get_grouping_information_unknown_value(self):
        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q3115846', 'count': '10'},
            {'grouping': 'http://www.wikidata.org/entity/Q5087901', 'count': '6'},
            {'grouping': 'http://www.wikidata.org/.well-known/genid/6ab4c2d7cb4ac72721335af5b8ba09c7', 'count': '2'},
            {'grouping': 'http://www.wikidata.org/.well-known/genid/1469448a291c6fbe5df8306cb52ef18b', 'count': '1'}
        ]
        expected = {
            'Q3115846': PropertyGrouping(title='Q3115846', count=10),
            'Q5087901': PropertyGrouping(title='Q5087901', count=6),
            'UNKNOWN_VALUE': UnknownValueGrouping(count=3)
        }
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count >= 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        result = self.stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_year(self):
        stats = PropertyStatistics(
            columns=self.columns,
            selector_sparql=u'wdt:P31 wd:Q41960',
            grouping_property=u'P577',
            grouping_type='year',
            property_threshold=10
        )

        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': '2001', 'count': '10'},
            {'grouping': '2002', 'count': '6'},
        ]
        expected = {
            '2001': YearGrouping(title='2001', count=10),
            '2002': YearGrouping(title='2002', count=6)
        }
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P577 ?date .\n"
            "  BIND(YEAR(?date) as ?grouping) .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count >= 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        result = stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_year_unknown_value(self):
        stats = PropertyStatistics(
            columns=self.columns,
            selector_sparql=u'wdt:P31 wd:Q41960',
            grouping_property=u'P577',
            grouping_type='year',
            property_threshold=10
        )

        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': '2001', 'count': '10'},
            {'grouping': '2002', 'count': '6'},
            {'grouping': '', 'count': '4'},
        ]
        expected = {
            '2001': YearGrouping(title='2001', count=10),
            '2002': YearGrouping(title='2002', count=6),
            'UNKNOWN_VALUE': UnknownValueGrouping(count=4)
        }
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P577 ?date .\n"
            "  BIND(YEAR(?date) as ?grouping) .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count >= 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        result = stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)


class TestGetHeader(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.stats.grouping_threshold = 7
        self.stats.property_threshold = 4

    def test_get_header(self):
        result = self.stats.get_header()
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 7 items)\n'
            '! colspan="6"|Top Properties (used at least 4 times per grouping)\n'
            '|-\n'
            '! Name\n'
            '! Count\n'
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{Property|P2}}\n'
            '! data-sort-type="number"|{{Property|P5}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            '! data-sort-type="number"|{{#language:xy}}\n'
        )
        self.assertEqual(result, expected)

    def test_get_header_with_higher_grouping(self):
        self.stats.higher_grouping = 'wdt:P17/wdt:P298'
        result = self.stats.get_header()
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="3" |Top groupings (Minimum 7 items)\n'
            '! colspan="6"|Top Properties (used at least 4 times per grouping)\n'
            '|-\n'
            '! \n'
            '! Name\n'
            '! Count\n'
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{Property|P2}}\n'
            '! data-sort-type="number"|{{Property|P5}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            '! data-sort-type="number"|{{#language:xy}}\n'
        )
        self.assertEqual(result, expected)


class MakeFooterTest(SparqlQueryTest, PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.mock_sparql_query.return_value.select.side_effect = [
            [{'count': '120'}],
            [{'count': '30'}],
            [{'count': '80'}],
            [{'count': '10'}],
            [{'count': '12'}],
            [{'count': '24'}],
            [{'count': '36'}],
        ]

    def test_make_footer(self):
        result = self.stats.make_footer()
        expected = (
            '|- class="sortbottom"\n'
            "|\'\'\'Totals\'\'\' <small>(all items)</small>:\n"
            "| 120\n"
            "| {{Integraality cell|25.0|30|column=P21}}\n"
            "| {{Integraality cell|66.67|80|column=P19}}\n"
            "| {{Integraality cell|8.33|10|column=P1/P2}}\n"
            "| {{Integraality cell|10.0|12|column=P3/Q4/P5}}\n"
            "| {{Integraality cell|20.0|24|column=Lbr}}\n"
            "| {{Integraality cell|30.0|36|column=Dxy}}\n"
            "|}\n"
        )
        self.assertEqual(result, expected)


class RetrieveDataTest(SparqlQueryTest, PropertyStatisticsTest):

    def test_retrieve_data_empty(self):
        result = self.stats.retrieve_data()
        expected = {}
        self.assertEqual(result, expected)

    def test_retrieve_data(self):
        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q3115846', 'count': '10'},
            {'grouping': 'http://www.wikidata.org/entity/Q5087901', 'count': '6'},
            {'grouping': 'http://www.wikidata.org/entity/Q623333', 'count': '6'}
        ]
        result = self.stats.retrieve_data()
        expected = {
            'Q3115846': PropertyGrouping(title='Q3115846', count=10),
            'Q5087901': PropertyGrouping(title='Q5087901', count=6),
            'Q623333': PropertyGrouping(title='Q623333', count=6)
        }
        self.assertEqual(result, expected)


class ProcessDataTest(SparqlQueryTest, PropertyStatisticsTest):

    def test_process_data_empty(self):
        result = self.stats.process_data({})
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="6"|Top Properties (used at least 10 times per grouping)\n'
            '|-\n'
            '! Name\n'
            '! Count\n'
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{Property|P2}}\n'
            '! data-sort-type="number"|{{Property|P5}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            '! data-sort-type="number"|{{#language:xy}}\n'
            '|- class="sortbottom"\n'
            "|'''Totals''' <small>(all items)</small>:\n"
            '| 1\n'
            '| {{Integraality cell|100.0|1|column=P21}}\n'
            '| {{Integraality cell|100.0|1|column=P19}}\n'
            '| {{Integraality cell|100.0|1|column=P1/P2}}\n'
            '| {{Integraality cell|100.0|1|column=P3/Q4/P5}}\n'
            '| {{Integraality cell|100.0|1|column=Lbr}}\n'
            '| {{Integraality cell|100.0|1|column=Dxy}}\n'
            '|}\n'
        )
        self.assertEqual(result, expected)

    def test_process_data(self):

        grouping_data = {
            'Q3115846': PropertyGrouping(title='Q3115846', count=10, cells=OrderedDict([
                ('P21', 10),
                ('P19', 8),
                ('P1P2', 2),
                ('P3Q4P5', 7),
                ('Lbr', 1),
                ('Dxy', 2)
            ])
            ),
            'Q5087901': PropertyGrouping(title='Q5087901', count=6, cells=OrderedDict([
                ('P21', 6),
                ('P19', 0),
                ('P1P2', 0),
                ('P3Q4P5', 0),
                ('Lbr', 0),
                ('Dxy', 0)
            ])
            ),
        }

        result = self.stats.process_data(grouping_data)
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="6"|Top Properties (used at least 10 times per grouping)\n'
            '|-\n'
            '! Name\n'
            '! Count\n'
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{Property|P2}}\n'
            '! data-sort-type="number"|{{Property|P5}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            '! data-sort-type="number"|{{#language:xy}}\n'
            '|-\n'
            '| {{Q|Q3115846}}\n'
            '| 10 \n'
            '| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n'
            '| {{Integraality cell|80.0|8|column=P19|grouping=Q3115846}}\n'
            '| {{Integraality cell|20.0|2|column=P1/P2|grouping=Q3115846}}\n'
            '| {{Integraality cell|70.0|7|column=P3/Q4/P5|grouping=Q3115846}}\n'
            '| {{Integraality cell|10.0|1|column=Lbr|grouping=Q3115846}}\n'
            '| {{Integraality cell|20.0|2|column=Dxy|grouping=Q3115846}}\n'
            '|-\n'
            '| {{Q|Q5087901}}\n'
            '| 6 \n'
            '| {{Integraality cell|100.0|6|column=P21|grouping=Q5087901}}\n'
            '| {{Integraality cell|0|0|column=P19|grouping=Q5087901}}\n'
            '| {{Integraality cell|0|0|column=P1/P2|grouping=Q5087901}}\n'
            '| {{Integraality cell|0|0|column=P3/Q4/P5|grouping=Q5087901}}\n'
            '| {{Integraality cell|0|0|column=Lbr|grouping=Q5087901}}\n'
            '| {{Integraality cell|0|0|column=Dxy|grouping=Q5087901}}\n'
            '|- class="sortbottom"\n'
            "|'''Totals''' <small>(all items)</small>:\n"
            '| 1\n'
            '| {{Integraality cell|100.0|1|column=P21}}\n'
            '| {{Integraality cell|100.0|1|column=P19}}\n'
            '| {{Integraality cell|100.0|1|column=P1/P2}}\n'
            '| {{Integraality cell|100.0|1|column=P3/Q4/P5}}\n'
            '| {{Integraality cell|100.0|1|column=Lbr}}\n'
            '| {{Integraality cell|100.0|1|column=Dxy}}\n'
            '|}\n'
        )

        self.assertEqual(result, expected)


class RetrieveAndProcessDataTest(SparqlQueryTest, PropertyStatisticsTest):

    def test_retrieve_and_process_data(self):
        self.mock_sparql_query.return_value.select.return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q3115846', 'count': '10'},
            {'grouping': 'http://www.wikidata.org/entity/Q5087901', 'count': '6'},
            {'grouping': 'http://www.wikidata.org/entity/Q623333', 'count': '6'}
        ]
        result = self.stats.retrieve_and_process_data()
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="6"|Top Properties (used at least 10 times per grouping)\n'
            '|-\n'
            '! Name\n'
            '! Count\n'
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{Property|P2}}\n'
            '! data-sort-type="number"|{{Property|P5}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            '! data-sort-type="number"|{{#language:xy}}\n'
            '|-\n'
            '| {{Q|Q3115846}}\n'
            '| 10 \n'
            '| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n'
            '| {{Integraality cell|100.0|10|column=P19|grouping=Q3115846}}\n'
            '| {{Integraality cell|100.0|10|column=P1/P2|grouping=Q3115846}}\n'
            '| {{Integraality cell|100.0|10|column=P3/Q4/P5|grouping=Q3115846}}\n'
            '| {{Integraality cell|100.0|10|column=Lbr|grouping=Q3115846}}\n'
            '| {{Integraality cell|100.0|10|column=Dxy|grouping=Q3115846}}\n'
            '|-\n'
            '| {{Q|Q5087901}}\n'
            '| 6 \n'
            '| {{Integraality cell|100.0|6|column=P21|grouping=Q5087901}}\n'
            '| {{Integraality cell|100.0|6|column=P19|grouping=Q5087901}}\n'
            '| {{Integraality cell|100.0|6|column=P1/P2|grouping=Q5087901}}\n'
            '| {{Integraality cell|100.0|6|column=P3/Q4/P5|grouping=Q5087901}}\n'
            '| {{Integraality cell|100.0|6|column=Lbr|grouping=Q5087901}}\n'
            '| {{Integraality cell|100.0|6|column=Dxy|grouping=Q5087901}}\n'
            '|-\n'
            '| {{Q|Q623333}}\n'
            '| 6 \n'
            '| {{Integraality cell|100.0|6|column=P21|grouping=Q623333}}\n'
            '| {{Integraality cell|100.0|6|column=P19|grouping=Q623333}}\n'
            '| {{Integraality cell|100.0|6|column=P1/P2|grouping=Q623333}}\n'
            '| {{Integraality cell|100.0|6|column=P3/Q4/P5|grouping=Q623333}}\n'
            '| {{Integraality cell|100.0|6|column=Lbr|grouping=Q623333}}\n'
            '| {{Integraality cell|100.0|6|column=Dxy|grouping=Q623333}}\n'
            '|- class="sortbottom"\n'
            "|'''Totals''' <small>(all items)</small>:\n"
            '| 10\n'
            '| {{Integraality cell|100.0|10|column=P21}}\n'
            '| {{Integraality cell|100.0|10|column=P19}}\n'
            '| {{Integraality cell|100.0|10|column=P1/P2}}\n'
            '| {{Integraality cell|100.0|10|column=P3/Q4/P5}}\n'
            '| {{Integraality cell|100.0|10|column=Lbr}}\n'
            '| {{Integraality cell|100.0|10|column=Dxy}}\n'
            '|}\n'
        )
        self.assertEqual(result, expected)
