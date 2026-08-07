# -*- coding: utf-8  -*-

import unittest

from ..column import (
    AllPropertiesReferenceCheck,
    AnyOfPropertiesReferenceCheck,
    AnyReferenceCheck,
    ColumnMaker,
    ColumnSyntaxException,
    DescriptionColumn,
    GoodReferenceCheck,
    LabelColumn,
    PropertyColumn,
    PropertyReferenceCheck,
    QualifierColumn,
    ReferenceColumn,
    SitelinkColumn,
)
from ..grouping import GroupingConfiguration, ItemGroupingType
from ..property_statistics import PropertyStatistics


class PropertyStatisticsTest(unittest.TestCase):
    def setUp(self):
        columns = [
            PropertyColumn(property="P21"),
            PropertyColumn(property="P19"),
            QualifierColumn(property="P1", qualifier="P2"),
            QualifierColumn(property="P3", value="Q4", qualifier="P5"),
            LabelColumn(language="br"),
            DescriptionColumn(language="xy"),
        ]
        self.grouping_configuration = GroupingConfiguration(
            predicate="wdt:P551", grouping_type=ItemGroupingType()
        )
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
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960
  FILTER(EXISTS {
    ?entity p:P19[]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  MINUS { ?entity wdt:P551 _:b28. }
  FILTER(EXISTS {
    ?entity p:P19[]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 ?grouping .
  FILTER(EXISTS {
    ?entity p:P19[]
  })
}
GROUP BY ?grouping
HAVING (?count >= 10)
ORDER BY DESC(?count)
LIMIT 1000
"""
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
        self.column = QualifierColumn("P669", qualifier="P670")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P670}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960
  FILTER(EXISTS {
    ?entity p:P669 [ ps:P669 [] ; pq:P670 [] ]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  MINUS { ?entity wdt:P551 _:b28. }
  FILTER(EXISTS {
    ?entity p:P669 [ ps:P669 [] ; pq:P670 [] ]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 ?grouping .
  FILTER(EXISTS {
    ?entity p:P669 [ ps:P669 [] ; pq:P670 [] ]
  })
}
GROUP BY ?grouping
HAVING (?count >= 10)
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)


class TestPropertyColumnWithQualifierAndLabel(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = QualifierColumn("P669", title="street", qualifier="P670")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P670|street]]\n'
        self.assertEqual(result, expected)


class TestPropertyColumnWithQualifierAndValue(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = QualifierColumn(property="P3", value="Q4", qualifier="P5")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P5}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960
  FILTER(EXISTS {
    ?entity p:P3 [ ps:P3 wd:Q4 ; pq:P5 [] ]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  MINUS { ?entity wdt:P551 _:b28. }
  FILTER(EXISTS {
    ?entity p:P3 [ ps:P3 wd:Q4 ; pq:P5 [] ]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 ?grouping .
  FILTER(EXISTS {
    ?entity p:P3 [ ps:P3 wd:Q4 ; pq:P5 [] ]
  })
}
GROUP BY ?grouping
HAVING (?count >= 10)
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)


class TestPropertyColumnWithQualifierAndValueAndTitle(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = QualifierColumn(
            property="P3", title="Some property", value="Q4", qualifier="P5"
        )

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P5|Some property]]\n'
        self.assertEqual(result, expected)


class TestPropertyColumnWithQualifierAndVariableValue(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = QualifierColumn(
            property="P166", value="?grouping", qualifier="P585"
        )

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 ?grouping .
  FILTER(EXISTS {
    ?entity p:P166 [ ps:P166 ?grouping ; pq:P585 [] ]
  })
}
GROUP BY ?grouping
HAVING (?count >= 10)
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960
  FILTER(EXISTS {
    ?entity p:P166 [ ps:P166 ?grouping ; pq:P585 [] ]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  MINUS { ?entity wdt:P551 _:b28. }
  FILTER(EXISTS {
    ?entity p:P166 [ ps:P166 ?grouping ; pq:P585 [] ]
  })
}
"""
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
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960
  FILTER(EXISTS {
    ?sitelink schema:about ?entity;
      schema:isPartOf <https://br.wikipedia.org/>.
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  MINUS { ?entity wdt:P551 _:b28. }
  FILTER(EXISTS {
    ?sitelink schema:about ?entity;
      schema:isPartOf <https://br.wikipedia.org/>.
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 ?grouping .
  FILTER(EXISTS {
    ?sitelink schema:about ?entity;
      schema:isPartOf <https://br.wikipedia.org/>.
  })
}
GROUP BY ?grouping
HAVING (?count >= 10)
ORDER BY DESC(?count)
LIMIT 1000
"""
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
        expected = QualifierColumn(property="P669", qualifier="P670")
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_title(self):
        key = "P669/P670"
        result = ColumnMaker.make(key, "street number")
        expected = QualifierColumn(
            property="P669", qualifier="P670", title="street number"
        )
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_value(self):
        key = "P553/Q17459/P670"
        result = ColumnMaker.make(key, None)
        expected = QualifierColumn(property="P553", value="Q17459", qualifier="P670")
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_value_and_title(self):
        key = "P553/Q17459/P670"
        result = ColumnMaker.make(key, "street number")
        expected = QualifierColumn(
            property="P553", value="Q17459", qualifier="P670", title="street number"
        )
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_variable_value(self):
        key = "P166/?grouping/P585"
        result = ColumnMaker.make(key, None)
        expected = QualifierColumn(property="P166", value="?grouping", qualifier="P585")
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_invalid_variable_value(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P166/?foo/P585", None)

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


class TestColumnMakerReference(PropertyStatisticsTest):
    def test_reference_any(self):
        result = ColumnMaker.make("P21/S*", None)
        expected = ReferenceColumn(property="P21")
        self.assertEqual(result, expected)

    def test_reference_with_title(self):
        result = ColumnMaker.make("P21/S*", "sourced")
        expected = ReferenceColumn(property="P21", title="sourced")
        self.assertEqual(result, expected)

    def test_reference_specific_property(self):
        result = ColumnMaker.make("P21/S248", None)
        expected = ReferenceColumn(
            property="P21", reference_check=PropertyReferenceCheck("P248")
        )
        self.assertEqual(result, expected)

    def test_reference_specific_property_with_title(self):
        result = ColumnMaker.make("P136/S248", "genre via")
        expected = ReferenceColumn(
            property="P136",
            reference_check=PropertyReferenceCheck("P248"),
            title="genre via",
        )
        self.assertEqual(result, expected)

    def test_reference_good(self):
        result = ColumnMaker.make("P21/S!", None)
        expected = ReferenceColumn(property="P21", reference_check=GoodReferenceCheck())
        self.assertEqual(result, expected)

    def test_reference_good_value_scoped(self):
        result = ColumnMaker.make("P27/Q142/S!", None)
        expected = ReferenceColumn(
            property="P27", value="Q142", reference_check=GoodReferenceCheck()
        )
        self.assertEqual(result, expected)

    def test_reference_multiple_properties(self):
        result = ColumnMaker.make("P21/S248;S854", None)
        expected = ReferenceColumn(
            property="P21",
            reference_check=AnyOfPropertiesReferenceCheck(["P248", "P854"]),
        )
        self.assertEqual(result, expected)

    def test_reference_multiple_properties_three(self):
        result = ColumnMaker.make("P21/S248;S854;S813", None)
        expected = ReferenceColumn(
            property="P21",
            reference_check=AnyOfPropertiesReferenceCheck(["P248", "P854", "P813"]),
        )
        self.assertEqual(result, expected)

    def test_reference_multiple_properties_invalid_part(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P21/S248;Sabc", None)

    def test_reference_all_properties(self):
        result = ColumnMaker.make("P21/S248+S304", None)
        expected = ReferenceColumn(
            property="P21",
            reference_check=AllPropertiesReferenceCheck(["P248", "P304"]),
        )
        self.assertEqual(result, expected)

    def test_reference_all_properties_three(self):
        result = ColumnMaker.make("P21/S248+S304+S813", None)
        expected = ReferenceColumn(
            property="P21",
            reference_check=AllPropertiesReferenceCheck(["P248", "P304", "P813"]),
        )
        self.assertEqual(result, expected)

    def test_reference_all_properties_invalid_part(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P21/S248+Sabc", None)

    def test_reference_property_value(self):
        result = ColumnMaker.make("P21/S248=Q19216625", None)
        expected = ReferenceColumn(
            property="P21",
            reference_check=PropertyReferenceCheck("P248", "Q19216625"),
        )
        self.assertEqual(result, expected)

    def test_reference_property_value_with_value(self):
        result = ColumnMaker.make("P27/Q142/S248=Q19216625", None)
        expected = ReferenceColumn(
            property="P27",
            value="Q142",
            reference_check=PropertyReferenceCheck("P248", "Q19216625"),
        )
        self.assertEqual(result, expected)

    def test_reference_property_value_with_qualifier(self):
        result = ColumnMaker.make("P21/P580/S248=Q19216625", None)
        expected = ReferenceColumn(
            property="P21",
            qualifier="P580",
            reference_check=PropertyReferenceCheck("P248", "Q19216625"),
        )
        self.assertEqual(result, expected)

    def test_reference_property_value_invalid_value(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P21/S248=P123", None)

    def test_reference_property_value_invalid_property(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P21/Sabc=Q123", None)

    def test_reference_unsupported_syntax(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P21/S+", None)

    def test_reference_unsupported_syntax_alpha(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P21/Sabc", None)

    def test_reference_value_scoped(self):
        result = ColumnMaker.make("P123/Q456/S*", None)
        expected = ReferenceColumn(property="P123", value="Q456")
        self.assertEqual(result, expected)

    def test_reference_value_scoped_grouping(self):
        result = ColumnMaker.make("P27/?grouping/S*", None)
        expected = ReferenceColumn(property="P27", value="?grouping")
        self.assertEqual(result, expected)

    def test_reference_value_scoped_with_specific_property(self):
        result = ColumnMaker.make("P27/Q142/S248", None)
        expected = ReferenceColumn(
            property="P27",
            value="Q142",
            reference_check=PropertyReferenceCheck("P248"),
        )
        self.assertEqual(result, expected)

    def test_reference_value_scoped_invalid_variable(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P27/?foo/S*", None)

    def test_reference_on_qualifier(self):
        result = ColumnMaker.make("P123/P789/S*", None)
        expected = ReferenceColumn(property="P123", qualifier="P789")
        self.assertEqual(result, expected)

    def test_reference_on_qualifier_with_value(self):
        result = ColumnMaker.make("P123/Q456/P789/S*", None)
        expected = ReferenceColumn(property="P123", value="Q456", qualifier="P789")
        self.assertEqual(result, expected)

    def test_reference_on_qualifier_with_specific_property(self):
        result = ColumnMaker.make("P123/P789/S248", None)
        expected = ReferenceColumn(
            property="P123",
            qualifier="P789",
            reference_check=PropertyReferenceCheck("P248"),
        )
        self.assertEqual(result, expected)

    def test_reference_on_qualifier_with_value_and_specific_property(self):
        result = ColumnMaker.make("P123/Q456/P789/S!", None)
        expected = ReferenceColumn(
            property="P123",
            value="Q456",
            qualifier="P789",
            reference_check=GoodReferenceCheck(),
        )
        self.assertEqual(result, expected)

    def test_reference_too_many_parts(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P1/Q2/P3/Q4/S*", None)


class TestListeriaKey(unittest.TestCase):
    def test_property(self):
        self.assertEqual(PropertyColumn("P136").get_listeria_key(), "P136")

    def test_property_with_qualifier(self):
        self.assertEqual(
            QualifierColumn("P669", qualifier="P670").get_listeria_key(), "P669/P670"
        )

    def test_property_with_qualifier_and_value(self):
        self.assertEqual(
            QualifierColumn(
                "P553", value="Q17459", qualifier="P670"
            ).get_listeria_key(),
            "P553/Q17459/P670",
        )

    def test_label(self):
        self.assertEqual(LabelColumn("de").get_listeria_key(), "label/de")

    def test_description(self):
        self.assertEqual(DescriptionColumn("de").get_listeria_key(), "description/de")

    def test_sitelink(self):
        self.assertIsNone(SitelinkColumn("brwiki").get_listeria_key())

    def test_reference(self):
        self.assertEqual(ReferenceColumn("P136").get_listeria_key(), "P136")


class TestReferenceColumn(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn("P19")

    def test_get_key(self):
        result = self.column.get_key()
        self.assertEqual(result, "P19/S*")

    def test_get_type_name(self):
        result = self.column.get_type_name()
        self.assertEqual(result, "reference")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P19}}📚\n'
        self.assertEqual(result, expected)

    def test_make_column_header_with_title(self):
        column = ReferenceColumn("P19", title="sourced birth")
        result = column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P19|sourced birth]]\n'
        self.assertEqual(result, expected)

    def test_format_html_snippet(self):
        result = self.column.format_html_snippet()
        expected = '<a href="https://wikidata.org/wiki/Property:P19">P19</a> referenced'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960
  FILTER(EXISTS {
    ?entity p:P19 [] .
    FILTER NOT EXISTS {
      ?entity p:P19 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  MINUS { ?entity wdt:P551 _:b28. }
  FILTER(EXISTS {
    ?entity p:P19 [] .
    FILTER NOT EXISTS {
      ?entity p:P19 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q41960 .
  ?entity wdt:P551 ?grouping .
  FILTER(EXISTS {
    ?entity p:P19 [] .
    FILTER NOT EXISTS {
      ?entity p:P19 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }
  })
}
GROUP BY ?grouping
HAVING (?count >= 10)
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)

    def test_get_filter_for_positive_query(self):
        result = self.column.get_filter_for_positive_query()
        expected = """
  ?entity p:P19 ?statement .
  ?statement ps:P19 ?value .
  FILTER NOT EXISTS {
    ?entity p:P19 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom []
    }
  }
"""
        self.assertEqual(result, expected)

    def test_get_filter_for_negative_query(self):
        result = self.column.get_filter_for_negative_query()
        expected = """
  OPTIONAL {
    ?entity p:P19 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom []
    }
  }
  OPTIONAL { ?entity p:P19 ?_any_stmt . }
  FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
"""
        self.assertEqual(result, expected)


class TestReferenceColumnWithTitle(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn("P19", title="sourced birth")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P19|sourced birth]]\n'
        self.assertEqual(result, expected)


class TestReferenceCheckStrategies(unittest.TestCase):
    def test_any_reference_check_pattern(self):
        check = AnyReferenceCheck()
        result = check.sparql_pattern()
        self.assertEqual(result, "?_unreferenced_stmt prov:wasDerivedFrom []")

    def test_any_reference_check_key_suffix(self):
        self.assertEqual(AnyReferenceCheck().key_suffix(), "S*")

    def test_any_reference_check_column_label_suffix(self):
        self.assertEqual(AnyReferenceCheck().column_label_suffix(), "📚")

    def test_any_reference_check_format_html_label(self):
        result = AnyReferenceCheck().format_html_label("<a>P19</a>")
        self.assertEqual(result, "<a>P19</a> referenced")

    def test_any_reference_check_equality(self):
        self.assertEqual(AnyReferenceCheck(), AnyReferenceCheck())

    def test_property_reference_check_pattern(self):
        check = PropertyReferenceCheck("P248")
        result = check.sparql_pattern()
        self.assertEqual(result, "?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 []")

    def test_property_reference_check_key_suffix(self):
        self.assertEqual(PropertyReferenceCheck("P248").key_suffix(), "S248")

    def test_property_reference_check_column_label_suffix(self):
        self.assertEqual(
            PropertyReferenceCheck("P248").column_label_suffix(),
            "📚{{Property|P248}}",
        )

    def test_property_reference_check_format_html_label(self):
        result = PropertyReferenceCheck("P248").format_html_label("<a>P19</a>")
        expected = (
            "<a>P19</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
        )
        self.assertEqual(result, expected)

    def test_property_reference_check_equality(self):
        self.assertEqual(PropertyReferenceCheck("P248"), PropertyReferenceCheck("P248"))
        self.assertNotEqual(
            PropertyReferenceCheck("P248"), PropertyReferenceCheck("P854")
        )

    def test_any_of_properties_reference_check_pattern(self):
        check = AnyOfPropertiesReferenceCheck(["P248", "P854"])
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "{ ?_ref pr:P248 [] } UNION { ?_ref pr:P854 [] }"
        )
        self.assertEqual(result, expected)

    def test_any_of_properties_reference_check_key_suffix(self):
        self.assertEqual(
            AnyOfPropertiesReferenceCheck(["P248", "P854"]).key_suffix(), "S248;S854"
        )

    def test_any_of_properties_reference_check_column_label_suffix(self):
        self.assertEqual(
            AnyOfPropertiesReferenceCheck(["P248", "P854"]).column_label_suffix(),
            "📚{{Property|P248}}/{{Property|P854}}",
        )

    def test_any_of_properties_reference_check_format_html_label(self):
        result = AnyOfPropertiesReferenceCheck(["P248", "P854"]).format_html_label(
            "<a>P19</a>"
        )
        expected = (
            "<a>P19</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
            " / "
            '<a href="https://wikidata.org/wiki/Property:P854">P854</a>'
        )
        self.assertEqual(result, expected)

    def test_any_of_properties_reference_check_equality(self):
        self.assertEqual(
            AnyOfPropertiesReferenceCheck(["P248", "P854"]),
            AnyOfPropertiesReferenceCheck(["P248", "P854"]),
        )
        self.assertNotEqual(
            AnyOfPropertiesReferenceCheck(["P248", "P854"]),
            AnyOfPropertiesReferenceCheck(["P248"]),
        )

    def test_all_properties_reference_check_pattern(self):
        check = AllPropertiesReferenceCheck(["P248", "P304"])
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "?_ref pr:P248 [] .\n"
            "?_ref pr:P304 [] ."
        )
        self.assertEqual(result, expected)

    def test_all_properties_reference_check_key_suffix(self):
        self.assertEqual(
            AllPropertiesReferenceCheck(["P248", "P304"]).key_suffix(), "S248+S304"
        )

    def test_all_properties_reference_check_column_label_suffix(self):
        self.assertEqual(
            AllPropertiesReferenceCheck(["P248", "P304"]).column_label_suffix(),
            "📚{{Property|P248}}+{{Property|P304}}",
        )

    def test_all_properties_reference_check_format_html_label(self):
        result = AllPropertiesReferenceCheck(["P248", "P304"]).format_html_label(
            "<a>P19</a>"
        )
        expected = (
            "<a>P19</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
            " + "
            '<a href="https://wikidata.org/wiki/Property:P304">P304</a>'
        )
        self.assertEqual(result, expected)

    def test_all_properties_reference_check_equality(self):
        self.assertEqual(
            AllPropertiesReferenceCheck(["P248", "P304"]),
            AllPropertiesReferenceCheck(["P248", "P304"]),
        )
        self.assertNotEqual(
            AllPropertiesReferenceCheck(["P248", "P304"]),
            AllPropertiesReferenceCheck(["P248"]),
        )

    def test_property_value_reference_check_pattern(self):
        check = PropertyReferenceCheck("P248", "Q19216625")
        result = check.sparql_pattern()
        expected = "?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 wd:Q19216625"
        self.assertEqual(result, expected)

    def test_property_value_reference_check_key_suffix(self):
        self.assertEqual(
            PropertyReferenceCheck("P248", "Q19216625").key_suffix(), "S248=Q19216625"
        )

    def test_property_value_reference_check_column_label_suffix(self):
        self.assertEqual(
            PropertyReferenceCheck("P248", "Q19216625").column_label_suffix(),
            "📚{{Property|P248}}={{Q|Q19216625}}",
        )

    def test_property_value_reference_check_format_html_label(self):
        result = PropertyReferenceCheck("P248", "Q19216625").format_html_label(
            "<a>P19</a>"
        )
        expected = (
            "<a>P19</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
            "="
            '<a href="https://wikidata.org/wiki/Q19216625">Q19216625</a>'
        )
        self.assertEqual(result, expected)

    def test_property_value_reference_check_equality(self):
        self.assertEqual(
            PropertyReferenceCheck("P248", "Q19216625"),
            PropertyReferenceCheck("P248", "Q19216625"),
        )
        self.assertNotEqual(
            PropertyReferenceCheck("P248", "Q19216625"),
            PropertyReferenceCheck("P248", "Q99999"),
        )
        self.assertNotEqual(
            PropertyReferenceCheck("P248", "Q19216625"),
            PropertyReferenceCheck("P854", "Q19216625"),
        )
        self.assertNotEqual(
            PropertyReferenceCheck("P248", "Q19216625"),
            PropertyReferenceCheck("P248"),
        )

    def test_different_checks_not_equal(self):
        self.assertNotEqual(AnyReferenceCheck(), PropertyReferenceCheck("P248"))
        self.assertNotEqual(AnyReferenceCheck(), GoodReferenceCheck())
        self.assertNotEqual(PropertyReferenceCheck("P248"), GoodReferenceCheck())
        self.assertNotEqual(
            PropertyReferenceCheck("P248"),
            AnyOfPropertiesReferenceCheck(["P248"]),
        )
        self.assertNotEqual(
            AnyOfPropertiesReferenceCheck(["P248", "P854"]),
            AllPropertiesReferenceCheck(["P248", "P304"]),
        )
        self.assertNotEqual(
            PropertyReferenceCheck("P248"),
            PropertyReferenceCheck("P248", "Q19216625"),
        )

    def test_good_reference_check_pattern(self):
        check = GoodReferenceCheck()
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "FILTER NOT EXISTS { ?_ref pr:P143 [] }\n"
            "FILTER NOT EXISTS { ?_ref pr:P3452 [] }\n"
            "FILTER NOT EXISTS { ?_ref pr:P887 [] }"
        )
        self.assertEqual(result, expected)

    def test_good_reference_check_key_suffix(self):
        self.assertEqual(GoodReferenceCheck().key_suffix(), "S!")

    def test_good_reference_check_column_label_suffix(self):
        self.assertEqual(GoodReferenceCheck().column_label_suffix(), "📚✓")

    def test_good_reference_check_format_html_label(self):
        result = GoodReferenceCheck().format_html_label("<a>P19</a>")
        self.assertEqual(result, "<a>P19</a> well-referenced")

    def test_good_reference_check_equality(self):
        self.assertEqual(GoodReferenceCheck(), GoodReferenceCheck())


class TestReferenceColumnSpecificProperty(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(
            "P19", reference_check=PropertyReferenceCheck("P248")
        )

    def test_get_key(self):
        result = self.column.get_key()
        self.assertEqual(result, "P19/S248")

    def test_get_listeria_key(self):
        result = self.column.get_listeria_key()
        self.assertEqual(result, "P19")

    def test_get_type_name(self):
        result = self.column.get_type_name()
        self.assertEqual(result, "reference")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P19}}📚{{Property|P248}}\n'
        self.assertEqual(result, expected)

    def test_make_column_header_with_title(self):
        column = ReferenceColumn(
            "P19", title="stated in", reference_check=PropertyReferenceCheck("P248")
        )
        result = column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P19|stated in]]\n'
        self.assertEqual(result, expected)

    def test_format_html_snippet(self):
        result = self.column.format_html_snippet()
        expected = (
            '<a href="https://wikidata.org/wiki/Property:P19">P19</a>'
            " referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
        )
        self.assertEqual(result, expected)

    def test_get_filter_for_info(self):
        result = self.column.get_filter_for_info()
        expected = """
    ?entity p:P19 [] .
    FILTER NOT EXISTS {
      ?entity p:P19 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 []
      }
    }"""
        self.assertEqual(result, expected)

    def test_get_filter_for_positive_query(self):
        result = self.column.get_filter_for_positive_query()
        expected = """
  ?entity p:P19 ?statement .
  ?statement ps:P19 ?value .
  FILTER NOT EXISTS {
    ?entity p:P19 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 []
    }
  }
"""
        self.assertEqual(result, expected)

    def test_get_filter_for_negative_query(self):
        result = self.column.get_filter_for_negative_query()
        expected = """
  OPTIONAL {
    ?entity p:P19 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 []
    }
  }
  OPTIONAL { ?entity p:P19 ?_any_stmt . }
  FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
"""
        self.assertEqual(result, expected)

    def test_equality(self):
        col1 = ReferenceColumn("P19", reference_check=PropertyReferenceCheck("P248"))
        col2 = ReferenceColumn("P19", reference_check=PropertyReferenceCheck("P248"))
        col3 = ReferenceColumn("P19", reference_check=PropertyReferenceCheck("P854"))
        col4 = ReferenceColumn("P19")
        self.assertEqual(col1, col2)
        self.assertNotEqual(col1, col3)
        self.assertNotEqual(col1, col4)


class TestReferenceColumnValueScoped(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn("P27", value="Q142")

    def test_get_key(self):
        self.assertEqual(self.column.get_key(), "P27/Q142/S*")

    def test_get_key_grouping(self):
        column = ReferenceColumn("P27", value="?grouping")
        self.assertEqual(column.get_key(), "P27/?grouping/S*")

    def test_get_filter_for_info(self):
        result = self.column.get_filter_for_info()
        expected = """
    ?entity p:P27 ?_s .
    ?_s ps:P27 wd:Q142 .
    FILTER NOT EXISTS {
      ?entity p:P27 ?_unreferenced_stmt .
      ?_unreferenced_stmt ps:P27 wd:Q142 .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }"""
        self.assertEqual(result, expected)

    def test_get_filter_for_info_grouping(self):
        column = ReferenceColumn("P27", value="?grouping")
        result = column.get_filter_for_info()
        expected = """
    ?entity p:P27 ?_s .
    ?_s ps:P27 ?grouping .
    FILTER NOT EXISTS {
      ?entity p:P27 ?_unreferenced_stmt .
      ?_unreferenced_stmt ps:P27 ?grouping .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }"""
        self.assertEqual(result, expected)

    def test_get_filter_for_positive_query(self):
        result = self.column.get_filter_for_positive_query()
        expected = """
  ?entity p:P27 ?statement .
  ?statement ps:P27 ?value .
  ?statement ps:P27 wd:Q142 .
  FILTER NOT EXISTS {
    ?entity p:P27 ?_unreferenced_stmt .
    ?_unreferenced_stmt ps:P27 wd:Q142 .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom []
    }
  }
"""
        self.assertEqual(result, expected)

    def test_get_filter_for_negative_query(self):
        result = self.column.get_filter_for_negative_query()
        expected = """
  OPTIONAL {
    ?entity p:P27 ?_unreferenced_stmt .
    ?_unreferenced_stmt ps:P27 wd:Q142 .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom []
    }
  }
  OPTIONAL { ?entity p:P27 ?_any_stmt .
    ?_any_stmt ps:P27 wd:Q142 . }
  FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
"""
        self.assertEqual(result, expected)

    def test_equality(self):
        col1 = ReferenceColumn("P27", value="Q142")
        col2 = ReferenceColumn("P27", value="Q142")
        col3 = ReferenceColumn("P27", value="Q183")
        col4 = ReferenceColumn("P27")
        self.assertEqual(col1, col2)
        self.assertNotEqual(col1, col3)
        self.assertNotEqual(col1, col4)


class TestReferenceColumnGood(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn("P19", reference_check=GoodReferenceCheck())

    def test_get_key(self):
        self.assertEqual(self.column.get_key(), "P19/S!")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P19}}📚✓\n'
        self.assertEqual(result, expected)

    def test_format_html_snippet(self):
        result = self.column.format_html_snippet()
        expected = (
            '<a href="https://wikidata.org/wiki/Property:P19">P19</a> well-referenced'
        )
        self.assertEqual(result, expected)

    def test_get_filter_for_info(self):
        result = self.column.get_filter_for_info()
        expected = """
    ?entity p:P19 [] .
    FILTER NOT EXISTS {
      ?entity p:P19 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
        FILTER NOT EXISTS { ?_ref pr:P143 [] }
        FILTER NOT EXISTS { ?_ref pr:P3452 [] }
        FILTER NOT EXISTS { ?_ref pr:P887 [] }
      }
    }"""
        self.assertEqual(result, expected)

    def test_get_filter_for_positive_query(self):
        result = self.column.get_filter_for_positive_query()
        expected = """
  ?entity p:P19 ?statement .
  ?statement ps:P19 ?value .
  FILTER NOT EXISTS {
    ?entity p:P19 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
      FILTER NOT EXISTS { ?_ref pr:P143 [] }
      FILTER NOT EXISTS { ?_ref pr:P3452 [] }
      FILTER NOT EXISTS { ?_ref pr:P887 [] }
    }
  }
"""
        self.assertEqual(result, expected)

    def test_get_filter_for_negative_query(self):
        result = self.column.get_filter_for_negative_query()
        expected = """
  OPTIONAL {
    ?entity p:P19 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
      FILTER NOT EXISTS { ?_ref pr:P143 [] }
      FILTER NOT EXISTS { ?_ref pr:P3452 [] }
      FILTER NOT EXISTS { ?_ref pr:P887 [] }
    }
  }
  OPTIONAL { ?entity p:P19 ?_any_stmt . }
  FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
"""
        self.assertEqual(result, expected)


class TestReferenceColumnQualifierScoped(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn("P123", qualifier="P789")

    def test_get_key(self):
        self.assertEqual(self.column.get_key(), "P123/P789/S*")

    def test_get_key_with_value(self):
        col = ReferenceColumn("P123", value="Q456", qualifier="P789")
        self.assertEqual(col.get_key(), "P123/Q456/P789/S*")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P789}}📚\n'
        self.assertEqual(result, expected)

    def test_format_html_snippet(self):
        result = self.column.format_html_snippet()
        expected = (
            '<a href="https://wikidata.org/wiki/Property:P123">P123</a>'
            ' qualifier <a href="https://wikidata.org/wiki/Property:P789">P789</a>'
            " referenced"
        )
        self.assertEqual(result, expected)

    def test_format_html_snippet_with_value(self):
        col = ReferenceColumn("P166", value="Q594550", qualifier="P585")
        result = col.format_html_snippet()
        expected = (
            '<a href="https://wikidata.org/wiki/Property:P166">P166</a>'
            " = Q594550"
            ' qualifier <a href="https://wikidata.org/wiki/Property:P585">P585</a>'
            " referenced"
        )
        self.assertEqual(result, expected)

    def test_get_filter_for_info(self):
        result = self.column.get_filter_for_info()
        expected = """
    ?entity p:P123 ?_s .
    ?_s pq:P789 [] .
    FILTER NOT EXISTS {
      ?entity p:P123 ?_unreferenced_stmt .
      ?_unreferenced_stmt pq:P789 [] .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }"""
        self.assertEqual(result, expected)

    def test_get_filter_for_info_with_value(self):
        col = ReferenceColumn("P123", value="Q456", qualifier="P789")
        result = col.get_filter_for_info()
        expected = """
    ?entity p:P123 ?_s .
    ?_s ps:P123 wd:Q456 .
    ?_s pq:P789 [] .
    FILTER NOT EXISTS {
      ?entity p:P123 ?_unreferenced_stmt .
      ?_unreferenced_stmt ps:P123 wd:Q456 .
      ?_unreferenced_stmt pq:P789 [] .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }"""
        self.assertEqual(result, expected)

    def test_get_filter_for_positive_query(self):
        result = self.column.get_filter_for_positive_query()
        expected = """
  ?entity p:P123 ?statement .
  ?statement ps:P123 ?value .
  ?statement pq:P789 [] .
  FILTER NOT EXISTS {
    ?entity p:P123 ?_unreferenced_stmt .
    ?_unreferenced_stmt pq:P789 [] .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom []
    }
  }
"""
        self.assertEqual(result, expected)

    def test_get_filter_for_negative_query(self):
        result = self.column.get_filter_for_negative_query()
        expected = """
  OPTIONAL {
    ?entity p:P123 ?_unreferenced_stmt .
    ?_unreferenced_stmt pq:P789 [] .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom []
    }
  }
  OPTIONAL { ?entity p:P123 ?_any_stmt .
    ?_any_stmt pq:P789 [] . }
  FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
"""
        self.assertEqual(result, expected)

    def test_equality(self):
        col1 = ReferenceColumn("P123", qualifier="P789")
        col2 = ReferenceColumn("P123", qualifier="P789")
        col3 = ReferenceColumn("P123", qualifier="P790")
        col4 = ReferenceColumn("P123")
        self.assertEqual(col1, col2)
        self.assertNotEqual(col1, col3)
        self.assertNotEqual(col1, col4)
