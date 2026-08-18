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
            PropertyColumn(property="P131"),
            QualifierColumn(property="P2929", qualifier="P462"),
            QualifierColumn(property="P1435", value="Q10387575", qualifier="P580"),
            LabelColumn(language="br"),
            DescriptionColumn(language="xy"),
        ]
        self.grouping_configuration = GroupingConfiguration(
            predicate="wdt:P17", grouping_type=ItemGroupingType()
        )
        self.stats = PropertyStatistics(
            columns=columns,
            grouping_configuration=self.grouping_configuration,
            selector_sparql="wdt:P31 wd:Q39715",
            property_threshold=10,
        )


class TestPropertyColumn(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = PropertyColumn("P131")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P131}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715
  FILTER(EXISTS {
    ?entity p:P131[]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  MINUS { ?entity wdt:P17 _:b28. }
  FILTER(EXISTS {
    ?entity p:P131[]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  ?entity wdt:P17 ?grouping .
  FILTER(EXISTS {
    ?entity p:P131[]
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
        self.column = PropertyColumn("P131", title="birth")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P131|birth]]\n'
        self.assertEqual(result, expected)


class TestPropertyColumnWithQualifier(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = QualifierColumn("P1030", qualifier="P805")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P805}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715
  FILTER(EXISTS {
    ?entity p:P1030 [ ps:P1030 [] ; pq:P805 [] ]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  MINUS { ?entity wdt:P17 _:b28. }
  FILTER(EXISTS {
    ?entity p:P1030 [ ps:P1030 [] ; pq:P805 [] ]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  ?entity wdt:P17 ?grouping .
  FILTER(EXISTS {
    ?entity p:P1030 [ ps:P1030 [] ; pq:P805 [] ]
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
        self.column = QualifierColumn("P1030", title="street", qualifier="P805")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P805|street]]\n'
        self.assertEqual(result, expected)


class TestPropertyColumnWithQualifierAndValue(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = QualifierColumn(
            property="P1435", value="Q10387575", qualifier="P580"
        )

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P580}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715
  FILTER(EXISTS {
    ?entity p:P1435 [ ps:P1435 wd:Q10387575 ; pq:P580 [] ]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        # Override column value: Q10387575 (from setUp) has no ungrouped lighthouses,
        # but Q21013851 does — ensuring the functional test returns count > 0.
        column = QualifierColumn(property="P1435", value="Q21013851", qualifier="P580")
        result = column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  MINUS { ?entity wdt:P17 _:b28. }
  FILTER(EXISTS {
    ?entity p:P1435 [ ps:P1435 wd:Q21013851 ; pq:P580 [] ]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  ?entity wdt:P17 ?grouping .
  FILTER(EXISTS {
    ?entity p:P1435 [ ps:P1435 wd:Q10387575 ; pq:P580 [] ]
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
            property="P1435", title="Some property", value="Q10387575", qualifier="P580"
        )

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P580|Some property]]\n'
        self.assertEqual(result, expected)


class TestPropertyColumnWithQualifierAndVariableValue(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = QualifierColumn(
            property="P17", value="?grouping", qualifier="P580"
        )

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  ?entity wdt:P17 ?grouping .
  FILTER(EXISTS {
    ?entity p:P17 [ ps:P17 ?grouping ; pq:P580 [] ]
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
  ?entity wdt:P31 wd:Q39715
  FILTER(EXISTS {
    ?entity p:P17 [ ps:P17 ?grouping ; pq:P580 [] ]
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  MINUS { ?entity wdt:P17 _:b28. }
  FILTER(EXISTS {
    ?entity p:P17 [ ps:P17 ?grouping ; pq:P580 [] ]
  })
}
"""
        self.assertEqual(result, expected)


class TestSitelinkColumn(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = SitelinkColumn("frwiki")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Q|Q8447}}\n'
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715
  FILTER(EXISTS {
    ?sitelink schema:about ?entity;
      schema:isPartOf <https://fr.wikipedia.org/>.
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        expected = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  MINUS { ?entity wdt:P17 _:b28. }
  FILTER(EXISTS {
    ?sitelink schema:about ?entity;
      schema:isPartOf <https://fr.wikipedia.org/>.
  })
}
"""
        self.assertEqual(result, expected)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        expected = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  ?entity wdt:P17 ?grouping .
  FILTER(EXISTS {
    ?sitelink schema:about ?entity;
      schema:isPartOf <https://fr.wikipedia.org/>.
  })
}
GROUP BY ?grouping
HAVING (?count >= 10)
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)


class TestDescriptionColumn(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = DescriptionColumn("de")

    def test_get_filter_for_positive_query(self):
        result = self.column.get_filter_for_positive_query()
        expected_fragment = """
  ?entity schema:description ?value .
  FILTER(LANG(?value) = "de")
"""
        self.assertEqual(result, (expected_fragment, ["?entity", "?value"]))


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
        key = "P2929/P462"
        result = ColumnMaker.make(key, None)
        expected = QualifierColumn(property="P2929", qualifier="P462")
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_title(self):
        key = "P2929/P462"
        result = ColumnMaker.make(key, "street number")
        expected = QualifierColumn(
            property="P2929", qualifier="P462", title="street number"
        )
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_value(self):
        key = "P553/Q17459/P462"
        result = ColumnMaker.make(key, None)
        expected = QualifierColumn(property="P553", value="Q17459", qualifier="P462")
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_value_and_title(self):
        key = "P553/Q17459/P462"
        result = ColumnMaker.make(key, "street number")
        expected = QualifierColumn(
            property="P553", value="Q17459", qualifier="P462", title="street number"
        )
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_variable_value(self):
        key = "P17/?grouping/P580"
        result = ColumnMaker.make(key, None)
        expected = QualifierColumn(property="P17", value="?grouping", qualifier="P580")
        self.assertEqual(result, expected)

    def test_property_with_qualifier_and_invalid_variable_value(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P17/?foo/P580", None)

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
            reference_check=AnyOfPropertiesReferenceCheck(
                [("P248", None), ("P854", None)]
            ),
        )
        self.assertEqual(result, expected)

    def test_reference_multiple_properties_three(self):
        result = ColumnMaker.make("P21/S248;S854;S813", None)
        expected = ReferenceColumn(
            property="P21",
            reference_check=AnyOfPropertiesReferenceCheck(
                [("P248", None), ("P854", None), ("P813", None)]
            ),
        )
        self.assertEqual(result, expected)

    def test_reference_multiple_properties_invalid_part(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P21/S248;Sabc", None)

    def test_reference_all_properties(self):
        result = ColumnMaker.make("P21/S248+S304", None)
        expected = ReferenceColumn(
            property="P21",
            reference_check=AllPropertiesReferenceCheck(
                [("P248", None), ("P304", None)]
            ),
        )
        self.assertEqual(result, expected)

    def test_reference_all_properties_three(self):
        result = ColumnMaker.make("P21/S248+S304+S813", None)
        expected = ReferenceColumn(
            property="P21",
            reference_check=AllPropertiesReferenceCheck(
                [("P248", None), ("P304", None), ("P813", None)]
            ),
        )
        self.assertEqual(result, expected)

    def test_reference_all_properties_invalid_part(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P21/S248+Sabc", None)

    def test_reference_all_properties_with_value(self):
        result = ColumnMaker.make("P21/S248=Q135436770+S813", None)
        expected = ReferenceColumn(
            property="P21",
            reference_check=AllPropertiesReferenceCheck(
                [("P248", "Q135436770"), ("P813", None)]
            ),
        )
        self.assertEqual(result, expected)

    def test_reference_multiple_properties_with_value(self):
        result = ColumnMaker.make("P21/S248=Q135436770;S854", None)
        expected = ReferenceColumn(
            property="P21",
            reference_check=AnyOfPropertiesReferenceCheck(
                [("P248", "Q135436770"), ("P854", None)]
            ),
        )
        self.assertEqual(result, expected)

    def test_reference_all_properties_with_value_invalid(self):
        with self.assertRaises(ColumnSyntaxException):
            ColumnMaker.make("P21/S248=P123+S813", None)

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
            QualifierColumn("P2929", qualifier="P462").get_listeria_key(), "P2929/P462"
        )

    def test_property_with_qualifier_and_value(self):
        self.assertEqual(
            QualifierColumn(
                "P553", value="Q17459", qualifier="P462"
            ).get_listeria_key(),
            "P553/Q17459/P462",
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
        self.column = ReferenceColumn("P131")

    def test_get_key(self):
        result = self.column.get_key()
        self.assertEqual(result, "P131/S*")

    def test_get_type_name(self):
        result = self.column.get_type_name()
        self.assertEqual(result, "reference")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P131}}📚\n'
        self.assertEqual(result, expected)

    def test_make_column_header_with_title(self):
        column = ReferenceColumn("P131", title="sourced birth")
        result = column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P131|sourced birth]]\n'
        self.assertEqual(result, expected)

    def test_format_html_snippet(self):
        result = self.column.format_html_snippet()
        expected = (
            '<a href="https://wikidata.org/wiki/Property:P131">P131</a> referenced'
        )
        self.assertEqual(result, expected)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        expected = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715
  FILTER(EXISTS {
    ?entity p:P131 [] .
    FILTER NOT EXISTS {
      ?entity p:P131 ?_unreferenced_stmt .
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
  ?entity wdt:P31 wd:Q39715 .
  MINUS { ?entity wdt:P17 _:b28. }
  FILTER(EXISTS {
    ?entity p:P131 [] .
    FILTER NOT EXISTS {
      ?entity p:P131 ?_unreferenced_stmt .
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
  ?entity wdt:P31 wd:Q39715 .
  ?entity wdt:P17 ?grouping .
  FILTER(EXISTS {
    ?entity p:P131 [] .
    FILTER NOT EXISTS {
      ?entity p:P131 ?_unreferenced_stmt .
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
        expected_fragment = """
  ?entity p:P131 ?statement .
  ?statement ps:P131 ?value .
  FILTER NOT EXISTS {
    ?entity p:P131 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom []
    }
  }
  ?statement prov:wasDerivedFrom ?_refNode .
  OPTIONAL { ?_refNode pr:P248 ?_refNode_P248 . }
  OPTIONAL { ?_refNode pr:P854 ?_refNode_P854 . }
  OPTIONAL { ?_refNode ?_refNode_fallback_prop ?_refNode_fallback . FILTER(STRSTARTS(STR(?_refNode_fallback_prop), "http://www.wikidata.org/prop/reference/P")) FILTER(?_refNode_fallback_prop NOT IN (pr:P248, pr:P854, pr:P813, pr:P4656, pr:P1065)) }
  OPTIONAL { ?_refNode ?_refNode_depri_prop ?_refNode_deprioritized . FILTER(?_refNode_depri_prop IN (pr:P813, pr:P4656, pr:P1065)) }
  BIND(COALESCE(?_refNode_P248, ?_refNode_P854, ?_refNode_fallback, ?_refNode_deprioritized) AS ?refValue)
  BIND(COALESCE(IF(BOUND(?_refNode_P248), wd:P248, 1/0), IF(BOUND(?_refNode_P854), wd:P854, 1/0), IRI(REPLACE(STR(?_refNode_fallback_prop), "http://www.wikidata.org/prop/reference/", "http://www.wikidata.org/entity/")), IRI(REPLACE(STR(?_refNode_depri_prop), "http://www.wikidata.org/prop/reference/", "http://www.wikidata.org/entity/"))) AS ?refProperty)
"""
        self.assertEqual(
            result,
            (expected_fragment, ["?entity", "?value", "?refProperty", "?refValue"]),
        )

    def test_get_filter_for_negative_query(self):
        result = self.column.get_filter_for_negative_query()
        expected_fragment = """
  OPTIONAL {
    ?entity p:P131 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom []
    }
  }
  OPTIONAL { ?entity p:P131 ?_any_stmt . }
  FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
  OPTIONAL { ?entity p:P131 ?_show_stmt . ?_show_stmt ps:P131 ?value . }
"""
        self.assertEqual(result, (expected_fragment, ["?entity", "?value"]))


class TestReferenceColumnWithTitle(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn("P131", title="sourced birth")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P131|sourced birth]]\n'
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
        result = AnyReferenceCheck().format_html_label("<a>P131</a>")
        self.assertEqual(result, "<a>P131</a> referenced")

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
        result = PropertyReferenceCheck("P248").format_html_label("<a>P131</a>")
        expected = (
            "<a>P131</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
        )
        self.assertEqual(result, expected)

    def test_property_reference_check_equality(self):
        self.assertEqual(PropertyReferenceCheck("P248"), PropertyReferenceCheck("P248"))
        self.assertNotEqual(
            PropertyReferenceCheck("P248"), PropertyReferenceCheck("P854")
        )

    def test_any_of_properties_reference_check_pattern(self):
        check = AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)])
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "{ ?_ref pr:P248 [] } UNION { ?_ref pr:P854 [] }"
        )
        self.assertEqual(result, expected)

    def test_any_of_properties_reference_check_key_suffix(self):
        self.assertEqual(
            AnyOfPropertiesReferenceCheck(
                [("P248", None), ("P854", None)]
            ).key_suffix(),
            "S248;S854",
        )

    def test_any_of_properties_reference_check_column_label_suffix(self):
        self.assertEqual(
            AnyOfPropertiesReferenceCheck(
                [("P248", None), ("P854", None)]
            ).column_label_suffix(),
            "📚{{Property|P248}}/{{Property|P854}}",
        )

    def test_any_of_properties_reference_check_format_html_label(self):
        result = AnyOfPropertiesReferenceCheck(
            [("P248", None), ("P854", None)]
        ).format_html_label("<a>P131</a>")
        expected = (
            "<a>P131</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
            " / "
            '<a href="https://wikidata.org/wiki/Property:P854">P854</a>'
        )
        self.assertEqual(result, expected)

    def test_any_of_properties_reference_check_equality(self):
        self.assertEqual(
            AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)]),
            AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)]),
        )
        self.assertNotEqual(
            AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)]),
            AnyOfPropertiesReferenceCheck([("P248", None)]),
        )

    def test_any_of_properties_reference_check_with_value_pattern(self):
        check = AnyOfPropertiesReferenceCheck([("P248", "Q135436770"), ("P854", None)])
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "{ ?_ref pr:P248 wd:Q135436770 } UNION { ?_ref pr:P854 [] }"
        )
        self.assertEqual(result, expected)

    def test_all_properties_reference_check_pattern(self):
        check = AllPropertiesReferenceCheck([("P248", None), ("P304", None)])
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "?_ref pr:P248 [] .\n"
            "?_ref pr:P304 [] ."
        )
        self.assertEqual(result, expected)

    def test_all_properties_reference_check_key_suffix(self):
        self.assertEqual(
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]).key_suffix(),
            "S248+S304",
        )

    def test_all_properties_reference_check_column_label_suffix(self):
        self.assertEqual(
            AllPropertiesReferenceCheck(
                [("P248", None), ("P304", None)]
            ).column_label_suffix(),
            "📚{{Property|P248}}+{{Property|P304}}",
        )

    def test_all_properties_reference_check_format_html_label(self):
        result = AllPropertiesReferenceCheck(
            [("P248", None), ("P304", None)]
        ).format_html_label("<a>P131</a>")
        expected = (
            "<a>P131</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
            " + "
            '<a href="https://wikidata.org/wiki/Property:P304">P304</a>'
        )
        self.assertEqual(result, expected)

    def test_all_properties_reference_check_equality(self):
        self.assertEqual(
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]),
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]),
        )
        self.assertNotEqual(
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]),
            AllPropertiesReferenceCheck([("P248", None)]),
        )

    def test_all_properties_reference_check_with_value_pattern(self):
        check = AllPropertiesReferenceCheck([("P248", "Q135436770"), ("P813", None)])
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "?_ref pr:P248 wd:Q135436770 .\n"
            "?_ref pr:P813 [] ."
        )
        self.assertEqual(result, expected)

    def test_all_properties_reference_check_with_value_key_suffix(self):
        self.assertEqual(
            AllPropertiesReferenceCheck(
                [("P248", "Q135436770"), ("P813", None)]
            ).key_suffix(),
            "S248=Q135436770+S813",
        )

    def test_all_properties_reference_check_with_value_column_label(self):
        self.assertEqual(
            AllPropertiesReferenceCheck(
                [("P248", "Q135436770"), ("P813", None)]
            ).column_label_suffix(),
            "📚{{Property|P248}}={{Q|Q135436770}}+{{Property|P813}}",
        )

    def test_all_properties_reference_check_with_value_html_label(self):
        result = AllPropertiesReferenceCheck(
            [("P248", "Q135436770"), ("P813", None)]
        ).format_html_label("<a>P136</a>")
        expected = (
            "<a>P136</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
            '=<a href="https://wikidata.org/wiki/Q135436770">Q135436770</a>'
            " + "
            '<a href="https://wikidata.org/wiki/Property:P813">P813</a>'
        )
        self.assertEqual(result, expected)

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
            "<a>P131</a>"
        )
        expected = (
            "<a>P131</a> referenced with "
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
            AnyOfPropertiesReferenceCheck([("P248", None)]),
        )
        self.assertNotEqual(
            AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)]),
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]),
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
        result = GoodReferenceCheck().format_html_label("<a>P131</a>")
        self.assertEqual(result, "<a>P131</a> well-referenced")

    def test_good_reference_check_equality(self):
        self.assertEqual(GoodReferenceCheck(), GoodReferenceCheck())


class TestReferenceColumnSpecificProperty(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(
            "P131", reference_check=PropertyReferenceCheck("P248")
        )

    def test_get_key(self):
        result = self.column.get_key()
        self.assertEqual(result, "P131/S248")

    def test_get_listeria_key(self):
        result = self.column.get_listeria_key()
        self.assertEqual(result, "P131")

    def test_get_type_name(self):
        result = self.column.get_type_name()
        self.assertEqual(result, "reference")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P131}}📚{{Property|P248}}\n'
        self.assertEqual(result, expected)

    def test_make_column_header_with_title(self):
        column = ReferenceColumn(
            "P131", title="stated in", reference_check=PropertyReferenceCheck("P248")
        )
        result = column.make_column_header()
        expected = '! data-sort-type="number"|[[Property:P131|stated in]]\n'
        self.assertEqual(result, expected)

    def test_format_html_snippet(self):
        result = self.column.format_html_snippet()
        expected = (
            '<a href="https://wikidata.org/wiki/Property:P131">P131</a>'
            " referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
        )
        self.assertEqual(result, expected)

    def test_get_filter_for_info(self):
        result = self.column.get_filter_for_info()
        expected = """
    ?entity p:P131 [] .
    FILTER NOT EXISTS {
      ?entity p:P131 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 []
      }
    }"""
        self.assertEqual(result, expected)

    def test_get_filter_for_positive_query(self):
        result = self.column.get_filter_for_positive_query()
        expected_fragment = """
  ?entity p:P131 ?statement .
  ?statement ps:P131 ?value .
  FILTER NOT EXISTS {
    ?entity p:P131 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 []
    }
  }
  ?statement prov:wasDerivedFrom/pr:P248 ?refValue .
"""
        self.assertEqual(
            result, (expected_fragment, ["?entity", "?value", "?refValue"])
        )

    def test_get_filter_for_negative_query(self):
        result = self.column.get_filter_for_negative_query()
        expected_fragment = """
  OPTIONAL {
    ?entity p:P131 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 []
    }
  }
  OPTIONAL { ?entity p:P131 ?_any_stmt . }
  FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
  OPTIONAL { ?entity p:P131 ?_show_stmt . ?_show_stmt ps:P131 ?value . }
"""
        self.assertEqual(result, (expected_fragment, ["?entity", "?value"]))

    def test_equality(self):
        col1 = ReferenceColumn("P131", reference_check=PropertyReferenceCheck("P248"))
        col2 = ReferenceColumn("P131", reference_check=PropertyReferenceCheck("P248"))
        col3 = ReferenceColumn("P131", reference_check=PropertyReferenceCheck("P854"))
        col4 = ReferenceColumn("P131")
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
        expected_fragment = """
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
  ?statement prov:wasDerivedFrom ?_refNode .
  OPTIONAL { ?_refNode pr:P248 ?_refNode_P248 . }
  OPTIONAL { ?_refNode pr:P854 ?_refNode_P854 . }
  OPTIONAL { ?_refNode ?_refNode_fallback_prop ?_refNode_fallback . FILTER(STRSTARTS(STR(?_refNode_fallback_prop), "http://www.wikidata.org/prop/reference/P")) FILTER(?_refNode_fallback_prop NOT IN (pr:P248, pr:P854, pr:P813, pr:P4656, pr:P1065)) }
  OPTIONAL { ?_refNode ?_refNode_depri_prop ?_refNode_deprioritized . FILTER(?_refNode_depri_prop IN (pr:P813, pr:P4656, pr:P1065)) }
  BIND(COALESCE(?_refNode_P248, ?_refNode_P854, ?_refNode_fallback, ?_refNode_deprioritized) AS ?refValue)
  BIND(COALESCE(IF(BOUND(?_refNode_P248), wd:P248, 1/0), IF(BOUND(?_refNode_P854), wd:P854, 1/0), IRI(REPLACE(STR(?_refNode_fallback_prop), "http://www.wikidata.org/prop/reference/", "http://www.wikidata.org/entity/")), IRI(REPLACE(STR(?_refNode_depri_prop), "http://www.wikidata.org/prop/reference/", "http://www.wikidata.org/entity/"))) AS ?refProperty)
"""
        self.assertEqual(
            result,
            (expected_fragment, ["?entity", "?value", "?refProperty", "?refValue"]),
        )

    def test_get_filter_for_negative_query(self):
        result = self.column.get_filter_for_negative_query()
        expected_fragment = """
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
  OPTIONAL { ?entity p:P27 ?_show_stmt . ?_show_stmt ps:P27 wd:Q142 . BIND(wd:Q142 AS ?value) }
"""
        self.assertEqual(result, (expected_fragment, ["?entity", "?value"]))

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
        self.column = ReferenceColumn("P131", reference_check=GoodReferenceCheck())

    def test_get_key(self):
        self.assertEqual(self.column.get_key(), "P131/S!")

    def test_make_column_header(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{Property|P131}}📚✓\n'
        self.assertEqual(result, expected)

    def test_format_html_snippet(self):
        result = self.column.format_html_snippet()
        expected = (
            '<a href="https://wikidata.org/wiki/Property:P131">P131</a> well-referenced'
        )
        self.assertEqual(result, expected)

    def test_get_filter_for_info(self):
        result = self.column.get_filter_for_info()
        expected = """
    ?entity p:P131 [] .
    FILTER NOT EXISTS {
      ?entity p:P131 ?_unreferenced_stmt .
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
        expected_fragment = """
  ?entity p:P131 ?statement .
  ?statement ps:P131 ?value .
  FILTER NOT EXISTS {
    ?entity p:P131 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
      FILTER NOT EXISTS { ?_ref pr:P143 [] }
      FILTER NOT EXISTS { ?_ref pr:P3452 [] }
      FILTER NOT EXISTS { ?_ref pr:P887 [] }
    }
  }
  ?statement prov:wasDerivedFrom ?_refNode .
  OPTIONAL { ?_refNode pr:P248 ?_refNode_P248 . }
  OPTIONAL { ?_refNode pr:P854 ?_refNode_P854 . }
  OPTIONAL { ?_refNode ?_refNode_fallback_prop ?_refNode_fallback . FILTER(STRSTARTS(STR(?_refNode_fallback_prop), "http://www.wikidata.org/prop/reference/P")) FILTER(?_refNode_fallback_prop NOT IN (pr:P248, pr:P854, pr:P813, pr:P4656, pr:P1065)) }
  OPTIONAL { ?_refNode ?_refNode_depri_prop ?_refNode_deprioritized . FILTER(?_refNode_depri_prop IN (pr:P813, pr:P4656, pr:P1065)) }
  BIND(COALESCE(?_refNode_P248, ?_refNode_P854, ?_refNode_fallback, ?_refNode_deprioritized) AS ?refValue)
  BIND(COALESCE(IF(BOUND(?_refNode_P248), wd:P248, 1/0), IF(BOUND(?_refNode_P854), wd:P854, 1/0), IRI(REPLACE(STR(?_refNode_fallback_prop), "http://www.wikidata.org/prop/reference/", "http://www.wikidata.org/entity/")), IRI(REPLACE(STR(?_refNode_depri_prop), "http://www.wikidata.org/prop/reference/", "http://www.wikidata.org/entity/"))) AS ?refProperty)
"""
        self.assertEqual(
            result,
            (expected_fragment, ["?entity", "?value", "?refProperty", "?refValue"]),
        )

    def test_get_filter_for_negative_query(self):
        result = self.column.get_filter_for_negative_query()
        expected_fragment = """
  OPTIONAL {
    ?entity p:P131 ?_unreferenced_stmt .
    FILTER NOT EXISTS {
      ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
      FILTER NOT EXISTS { ?_ref pr:P143 [] }
      FILTER NOT EXISTS { ?_ref pr:P3452 [] }
      FILTER NOT EXISTS { ?_ref pr:P887 [] }
    }
  }
  OPTIONAL { ?entity p:P131 ?_any_stmt . }
  FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
  OPTIONAL { ?entity p:P131 ?_show_stmt . ?_show_stmt ps:P131 ?value . }
"""
        self.assertEqual(result, (expected_fragment, ["?entity", "?value"]))


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
        col = ReferenceColumn("P17", value="Q594550", qualifier="P580")
        result = col.format_html_snippet()
        expected = (
            '<a href="https://wikidata.org/wiki/Property:P17">P17</a>'
            " = Q594550"
            ' qualifier <a href="https://wikidata.org/wiki/Property:P580">P580</a>'
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
        expected_fragment = """
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
  ?statement prov:wasDerivedFrom ?_refNode .
  OPTIONAL { ?_refNode pr:P248 ?_refNode_P248 . }
  OPTIONAL { ?_refNode pr:P854 ?_refNode_P854 . }
  OPTIONAL { ?_refNode ?_refNode_fallback_prop ?_refNode_fallback . FILTER(STRSTARTS(STR(?_refNode_fallback_prop), "http://www.wikidata.org/prop/reference/P")) FILTER(?_refNode_fallback_prop NOT IN (pr:P248, pr:P854, pr:P813, pr:P4656, pr:P1065)) }
  OPTIONAL { ?_refNode ?_refNode_depri_prop ?_refNode_deprioritized . FILTER(?_refNode_depri_prop IN (pr:P813, pr:P4656, pr:P1065)) }
  BIND(COALESCE(?_refNode_P248, ?_refNode_P854, ?_refNode_fallback, ?_refNode_deprioritized) AS ?refValue)
  BIND(COALESCE(IF(BOUND(?_refNode_P248), wd:P248, 1/0), IF(BOUND(?_refNode_P854), wd:P854, 1/0), IRI(REPLACE(STR(?_refNode_fallback_prop), "http://www.wikidata.org/prop/reference/", "http://www.wikidata.org/entity/")), IRI(REPLACE(STR(?_refNode_depri_prop), "http://www.wikidata.org/prop/reference/", "http://www.wikidata.org/entity/"))) AS ?refProperty)
"""
        self.assertEqual(
            result,
            (expected_fragment, ["?entity", "?value", "?refProperty", "?refValue"]),
        )

    def test_get_filter_for_negative_query(self):
        result = self.column.get_filter_for_negative_query()
        expected_fragment = """
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
  OPTIONAL { ?entity p:P123 ?_show_stmt . ?_show_stmt ps:P123 ?value . }
"""
        self.assertEqual(result, (expected_fragment, ["?entity", "?value"]))

    def test_equality(self):
        col1 = ReferenceColumn("P123", qualifier="P789")
        col2 = ReferenceColumn("P123", qualifier="P789")
        col3 = ReferenceColumn("P123", qualifier="P790")
        col4 = ReferenceColumn("P123")
        self.assertEqual(col1, col2)
        self.assertNotEqual(col1, col3)
        self.assertNotEqual(col1, col4)
