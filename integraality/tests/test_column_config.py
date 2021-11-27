# -*- coding: utf-8  -*-

import unittest

from column_config import (
    ColumnConfigMaker,
    ColumnSyntaxException,
    DescriptionConfig,
    LabelConfig,
    PropertyConfig
)
from property_statistics import PropertyStatistics


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

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = (
            "\n"
            "SELECT (COUNT(*) AS ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  MINUS { ?entity wdt:P551 _:b28. }\n"
            "  FILTER(EXISTS {\n"
            "    ?entity p:P19[]\n"
            "  })\n"
            "}\n"
        )
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  FILTER(EXISTS {\n"
            "    ?entity p:P19[]\n"
            "  })\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count >= 10)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
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

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = (
            "\n"
            "SELECT (COUNT(*) AS ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  MINUS { ?entity wdt:P551 _:b28. }\n"
            "  FILTER(EXISTS {\n"
            "    ?entity p:P669 [ ps:P669 [] ; pq:P670 [] ]\n"
            "  })\n"
            "}\n"
        )
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  FILTER(EXISTS {\n"
            "    ?entity p:P669 [ ps:P669 [] ; pq:P670 [] ]\n"
            "  })\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count >= 10)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
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

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = (
            "\n"
            "SELECT (COUNT(*) AS ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  MINUS { ?entity wdt:P551 _:b28. }\n"
            "  FILTER(EXISTS {\n"
            "    ?entity p:P3 [ ps:P3 Q4 ; pq:P5 [] ]\n"
            "  })\n"
            "}\n"
        )
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960 .\n"
            "  ?entity wdt:P551 ?grouping .\n"
            "  FILTER(EXISTS {\n"
            "    ?entity p:P3 [ ps:P3 Q4 ; pq:P5 [] ]\n"
            "  })\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count >= 10)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
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


class TestColumnConfigMaker(PropertyStatisticsTest):

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

    def test_aliases(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnConfigMaker.make('Axy', None)

    def test_unknown_syntax(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnConfigMaker.make('SomethingSomething', None)
