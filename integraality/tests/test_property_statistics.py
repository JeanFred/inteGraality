# -*- coding: utf-8  -*-
"""Unit tests for functions.py."""

import unittest
from collections import OrderedDict
from unittest.mock import patch

from property_statistics import (
    ColumnConfigMaker,
    DescriptionConfig,
    LabelConfig,
    PropertyConfig,
    PropertyStatistics,
    QueryException
)


class PropertyStatisticsTest(unittest.TestCase):

    def setUp(self):
        columns = [
            PropertyConfig(property='P21'),
            PropertyConfig(property='P19'),
            PropertyConfig(property='P1', qualifier='P2'),
            PropertyConfig(property='P3', value='Q4', qualifier='P5'),
            LabelConfig(language='br'),
            DescriptionConfig(language='xy'),
        ]
        self.stats = PropertyStatistics(
            columns=columns,
            selector_sparql=u'wdt:P31 wd:Q41960',
            grouping_property=u'P551',
            property_threshold=10
        )


class TestPropertyConfig(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.column = PropertyConfig('P19')

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = u'! data-sort-type="number"|{{Property|P19}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = (
            "\n"
            "SELECT (COUNT(*) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960\n"
            "  FILTER(EXISTS {\n"
            "    ?entity p:P19[]\n"
            "  })\n"
            "}\n"
        )
        self.assertEqual(result, expected)


class TestPropertyConfigWithTitle(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.column = PropertyConfig('P19', title="birth")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = u'! data-sort-type="number"|[[Property:P19|birth]]\n'
        self.assertEqual(result, expected)


class TestPropertyConfigWithQualifier(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.column = PropertyConfig('P669', qualifier='P670')

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = u'! data-sort-type="number"|{{Property|P670}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = (
            "\n"
            "SELECT (COUNT(*) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960\n"
            "  FILTER(EXISTS {\n"
            "    ?entity p:P669 [ ps:P669 [] ; pq:P670 [] ]\n"
            "  })\n"
            "}\n"
        )
        self.assertEqual(result, expected)


class TestPropertyConfigWithQualifierAndLabel(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.column = PropertyConfig('P669', title="street", qualifier='P670')

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = u'! data-sort-type="number"|[[Property:P670|street]]\n'
        self.assertEqual(result, expected)


class TestPropertyConfigWithQualifierAndValue(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.column = PropertyConfig(property='P3', value='Q4', qualifier='P5')

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = u'! data-sort-type="number"|{{Property|P5}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = (
            "\n"
            "SELECT (COUNT(*) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960\n"
            "  FILTER(EXISTS {\n"
            "    ?entity p:P3 [ ps:P3 Q4 ; pq:P5 [] ]\n"
            "  })\n"
            "}\n"
        )
        self.assertEqual(result, expected)


class TestPropertyConfigWithQualifierAndValueAndTitle(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.column = PropertyConfig(property='P3', title="Some property", value='Q4', qualifier='P5')

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = u'! data-sort-type="number"|[[Property:P5|Some property]]\n'
        self.assertEqual(result, expected)


class TestColumnConfigMaker(unittest.TestCase):

    def test_property_without_title(self):
        result = ColumnConfigMaker.make('P136', None)
        expected = PropertyConfig(property='P136')
        self.assertEqual(result, expected)

    def test_property_with_title(self):
        result = ColumnConfigMaker.make('P136', 'genre')
        expected = PropertyConfig(property='P136', title='genre')
        self.assertEqual(result, expected)

    def test_property_with_qualifier(self):
        key = 'P669/P670'
        result = ColumnConfigMaker.make(key, None)
        expected = PropertyConfig(property='P669', qualifier='P670')
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_title(self):
        key = 'P669/P670'
        result = ColumnConfigMaker.make(key, 'street number')
        expected = PropertyConfig(property='P669', qualifier='P670', title="street number")
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_value(self):
        key = 'P553/Q17459/P670'
        result = ColumnConfigMaker.make(key, None)
        expected = PropertyConfig(property='P553', value='Q17459', qualifier='P670')
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_value_and_title(self):
        key = 'P553/Q17459/P670'
        result = ColumnConfigMaker.make(key, 'street number')
        expected = PropertyConfig(property='P553', value='Q17459', qualifier='P670', title='street number')
        self.assertEqual(result, expected)

    def test_label(self):
        result = ColumnConfigMaker.make('Lxy', None)
        expected = LabelConfig(language='xy')
        self.assertEqual(result, expected)

    def test_description(self):
        result = ColumnConfigMaker.make('Dxy', None)
        expected = DescriptionConfig(language='xy')
        self.assertEqual(result, expected)


class SparqlQueryTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        patcher = patch('pywikibot.data.sparql.SparqlQuery', autospec=True)
        self.mock_sparql_query = patcher.start()
        self.addCleanup(patcher.stop)

    def assert_query_called(self, query):
        self.mock_sparql_query.return_value.select.assert_called_once_with(query)


class TestLabelConfig(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.column = LabelConfig('br')

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
            "SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {\n"
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
            "GROUP BY ?grouping\n"
            "ORDER BY DESC (?count)\n"
            "LIMIT 10\n"
        )
        print(result)
        print(query)
        self.assertEqual(result, query)


class TestDescriptionConfig(PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.column = DescriptionConfig('br')

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
            "SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {\n"
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
            "GROUP BY ?grouping\n"
            "ORDER BY DESC (?count)\n"
            "LIMIT 10\n"
        )

        self.assertEqual(result, query)


class FormatHigherGroupingTextTest(SparqlQueryTest, PropertyStatisticsTest):

    def test_format_higher_grouping_text_default_qitem(self):
        result = self.stats.format_higher_grouping_text("Q1")
        expected = '| data-sort-value="Q1"| {{Q|Q1}}\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_string(self):
        result = self.stats.format_higher_grouping_text("foo")
        expected = '| data-sort-value="foo"| foo\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_country(self):
        self.stats.higher_grouping_type = "country"
        result = self.stats.format_higher_grouping_text("AT")
        expected = '| data-sort-value="AT"| {{Flag|AT}}\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_image(self):
        text = "http://commons.wikimedia.org/wiki/Special:FilePath/US%20CDC%20logo.svg"
        result = self.stats.format_higher_grouping_text(text)
        expected = '| data-sort-value="US%20CDC%20logo.svg"| [[File:US%20CDC%20logo.svg|center|100px]]\n'
        self.assertEqual(result, expected)


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
            "| No grouping \n"
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
            "| No grouping \n"
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
        self.stats.column_data = {
            'P21': OrderedDict([('Q3115846', 10), ('Q5087901', 6)]),
            'P19': OrderedDict([('Q3115846', 8), ('Q2166574', 5)]),
            'P1P2': OrderedDict([('Q3115846', 2), ('Q2166574', 9)]),
            'P3Q4P5': OrderedDict([('Q3115846', 7), ('Q2166574', 1)]),
            'Lbr': OrderedDict([('Q3115846', 1), ('Q2166574', 2)]),
            'Dxy': OrderedDict([('Q3115846', 2), ('Q2166574', 1)]),
        }

    def test_make_stats_for_one_grouping(self):
        result = self.stats.make_stats_for_one_grouping("Q3115846", 10, None)
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

    def test_make_stats_for_one_grouping_with_higher_grouping(self):
        self.stats.higher_grouping = "wdt:P17/wdt:P298"
        result = self.stats.make_stats_for_one_grouping("Q3115846", 10, "Q1")
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
    def test_make_stats_for_one_grouping_with_grouping_link(self, mock_item_page):
        mock_item_page.return_value.labels = {'en': 'Bar'}
        self.stats.grouping_link = "Foo"
        result = self.stats.make_stats_for_one_grouping("Q3115846", 10, None)
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


class GetQueryForItemsForPropertyPositive(PropertyStatisticsTest):

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive('P21', 'Q3115846')
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
        result = self.stats.get_query_for_items_for_property_positive('P21', self.stats.GROUP_MAPPING.NO_GROUPING)
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
        result = self.stats.get_query_for_items_for_property_positive('P21', self.stats.GROUP_MAPPING.TOTALS)
        expected = """
SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity p:P21 ?prop . OPTIONAL { ?prop ps:P21 ?value }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_label(self):
        result = self.stats.get_query_for_items_for_property_positive('Lbr', 'Q3115846')
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


class GetQueryForItemsForPropertyNegative(PropertyStatisticsTest):

    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative('P21', 'Q3115846')
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
        result = self.stats.get_query_for_items_for_property_negative('P21', self.stats.GROUP_MAPPING.NO_GROUPING)
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
        result = self.stats.get_query_for_items_for_property_negative('P21', self.stats.GROUP_MAPPING.TOTALS)
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
        result = self.stats.get_query_for_items_for_property_negative('Lbr', 'Q3115846')
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


class GetCountFromSparqlTest(SparqlQueryTest, PropertyStatisticsTest):

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


class SparqlCountTest(SparqlQueryTest, PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.mock_sparql_query.return_value.select.return_value = [{'count': '18'}]

    def test_get_property_info_no_grouping(self):
        result = self.stats.get_property_info_no_grouping('P1')
        query = (
            "\n"
            "SELECT (COUNT(*) AS ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  MINUS { ?entity wdt:P551 _:b28. }\n"
            "  FILTER(EXISTS { ?entity p:P1 _:b29. })\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "ORDER BY DESC (?count)\n"
            "LIMIT 10\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, 18)

    def test_get_qualifier_info_no_grouping(self):
        result = self.stats.get_qualifier_info_no_grouping('P1', 'P2')
        query = (
            "\n"
            "SELECT (COUNT(*) AS ?count) WHERE {\n"
            "    ?entity wdt:P31 wd:Q41960 .\n"
            "    MINUS { ?entity wdt:P551 _:b28. }\n"
            "    FILTER EXISTS { ?entity p:P1 [ ps:P1 [] ; pq:P2 [] ] } .\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "ORDER BY DESC (?count)\n"
            "LIMIT 10\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, 18)

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
        expected = (
            OrderedDict([('Q3115846', 10), ('Q5087901', 6), ('Q623333', 6)]),
            OrderedDict()
        )
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {\n"
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
        expected = (
            OrderedDict([('Q3115846', 10), ('Q5087901', 6), ('Q623333', 6)]),
            OrderedDict()
        )
        self.stats.grouping_threshold = 5
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {\n"
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
        expected = (
            OrderedDict([('Q3115846', 10), ('Q5087901', 6), ('Q623333', 6)]),
            OrderedDict([('Q3115846', 'NZL'), ('Q5087901', 'USA'), ('Q623333', 'USA')])
        )
        self.stats.higher_grouping = 'wdt:P17/wdt:P298'
        query = (
            "\n"
            "SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) "
            "(COUNT(DISTINCT *) as ?count) WHERE {\n"
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
            "SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {\n"
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


class GetInfoTest(SparqlQueryTest, PropertyStatisticsTest):

    def setUp(self):
        super().setUp()
        self.sparql_return_value = [
            {'grouping': 'http://www.wikidata.org/entity/Q3115846', 'count': '10'},
            {'grouping': 'http://www.wikidata.org/entity/Q5087901', 'count': '6'},
            {'grouping': 'http://www.wikidata.org/entity/Q623333', 'count': '6'}
        ]
        self.expected = OrderedDict([('Q3115846', 10), ('Q5087901', 6), ('Q623333', 6)])


class GetPropertyInfoTest(GetInfoTest):

    def test_get_property_info(self):
        self.mock_sparql_query.return_value.select.return_value = self.sparql_return_value
        result = self.stats.get_property_info('P1')
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  FILTER EXISTS { ?entity p:P1 [] } .\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count >= 10)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, self.expected)

    def test_get_property_info_empty_result(self):
        self.mock_sparql_query.return_value.select.return_value = None
        expected = None
        result = self.stats.get_property_info('P1')
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  FILTER EXISTS { ?entity p:P1 [] } .\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count >= 10)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, expected)


class GetQualifierInfoTest(GetInfoTest):

    def test_get_qualifier_info(self):
        self.mock_sparql_query.return_value.select.return_value = self.sparql_return_value

        result = self.stats.get_qualifier_info('P1', qualifier="P2")
        query = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  FILTER EXISTS { ?entity p:P1 [ ps:P1 [] ; pq:P2 [] ] } .\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count >= 10)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assert_query_called(query)
        self.assertEqual(result, self.expected)


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
