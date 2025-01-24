# -*- coding: utf-8  -*-

import unittest

from column import (
    ColumnMaker,
    ColumnSyntaxException,
    DescriptionColumn,
    LabelColumn,
    PropertyColumn,
    SitelinkColumn,
)
from grouping import ItemGroupingConfiguration
from property_statistics import PropertyStatistics


class PropertyStatisticsTest(unittest.TestCase):
    def setUp(self):
        columns = [
            PropertyColumn(property="P21"),
            PropertyColumn(property="P19"),
            PropertyColumn(property="P1", qualifier="P2"),
            PropertyColumn(property="P3", value="Q4", qualifier="P5"),
            LabelColumn(language="br"),
            DescriptionColumn(language="xy"),
        ]
        self.grouping_configuration = ItemGroupingConfiguration("P551")
        self.stats = PropertyStatistics(
            columns=columns,
            grouping_configuration=self.grouping_configuration,
            selector_sparql="wdt:P31 wd:Q41960",
            property_threshold=10,
        )


class TestPropertyColumn(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = PropertyColumn("P19")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P19}}\n'
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


class TestPropertyColumnWithTitle(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = PropertyColumn("P19", title="birth")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P19|birth]]\n'
        self.assertEqual(result, expected)


class TestPropertyColumnWithQualifier(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = PropertyColumn("P669", qualifier="P670")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P670}}\n'
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


class TestPropertyColumnWithQualifierAndLabel(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = PropertyColumn("P669", title="street", qualifier="P670")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P670|street]]\n'
        self.assertEqual(result, expected)


class TestPropertyColumnWithQualifierAndValue(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = PropertyColumn(property="P3", value="Q4", qualifier="P5")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P5}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = (
            "\n"
            "SELECT (COUNT(*) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960\n"
            "  FILTER(EXISTS {\n"
            "    ?entity p:P3 [ ps:P3 wd:Q4 ; pq:P5 [] ]\n"
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
            "    ?entity p:P3 [ ps:P3 wd:Q4 ; pq:P5 [] ]\n"
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
            "    ?entity p:P3 [ ps:P3 wd:Q4 ; pq:P5 [] ]\n"
            "  })\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count >= 10)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assertEqual(result, expected)


class TestPropertyColumnWithQualifierAndValueAndTitle(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = PropertyColumn(
            property="P3", title="Some property", value="Q4", qualifier="P5"
        )

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P5|Some property]]\n'
        self.assertEqual(result, expected)


class TestSitelinkColumn(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = SitelinkColumn("brwiki")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Q|Q846871}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = (
            "\n"
            "SELECT (COUNT(*) as ?count) WHERE {\n"
            "  ?entity wdt:P31 wd:Q41960\n"
            "  FILTER(EXISTS {\n"
            "    ?sitelink schema:about ?entity;\n"
            "      schema:isPartOf <https://br.wikipedia.org/>.\n"
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
            "    ?sitelink schema:about ?entity;\n"
            "      schema:isPartOf <https://br.wikipedia.org/>.\n"
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
            "    ?sitelink schema:about ?entity;\n"
            "      schema:isPartOf <https://br.wikipedia.org/>.\n"
            "  })\n"
            "}\n"
            "GROUP BY ?grouping\n"
            "HAVING (?count >= 10)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assertEqual(result, expected)


class TestColumnMaker(PropertyStatisticsTest):
    def test_property_without_title(self):
        result = ColumnMaker.make("P136", None)
        expected = PropertyColumn(property="P136")
        self.assertEqual(result, expected)

    def test_property_with_title(self):
        result = ColumnMaker.make("P136", "genre")
        expected = PropertyColumn(property="P136", title="genre")
        self.assertEqual(result, expected)

    def test_property_with_qualifier(self):
        key = "P669/P670"
        result = ColumnMaker.make(key, None)
        expected = PropertyColumn(property="P669", qualifier="P670")
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_title(self):
        key = "P669/P670"
        result = ColumnMaker.make(key, "street number")
        expected = PropertyColumn(
            property="P669", qualifier="P670", title="street number"
        )
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_value(self):
        key = "P553/Q17459/P670"
        result = ColumnMaker.make(key, None)
        expected = PropertyColumn(property="P553", value="Q17459", qualifier="P670")
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_value_and_title(self):
        key = "P553/Q17459/P670"
        result = ColumnMaker.make(key, "street number")
        expected = PropertyColumn(
            property="P553", value="Q17459", qualifier="P670", title="street number"
        )
        self.assertEqual(result, expected)

    def test_label(self):
        result = ColumnMaker.make("Lxy", None)
        expected = LabelColumn(language="xy")
        self.assertEqual(result, expected)

    def test_description(self):
        result = ColumnMaker.make("Dxy", None)
        expected = DescriptionColumn(language="xy")
        self.assertEqual(result, expected)

    def test_aliases(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("Axy", None)

    def test_sitelink(self):
        result = ColumnMaker.make("brwiki", None)
        expected = SitelinkColumn("brwiki")
        self.assertEqual(result, expected)

    def test_unknown_syntax(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("SomethingSomething", None)
