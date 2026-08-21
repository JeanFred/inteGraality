# -*- coding: utf-8  -*-
"""Unit tests for functions.py."""

import unittest
from collections import OrderedDict
from unittest.mock import create_autospec, patch

from ..column import (
    DescriptionColumn,
    LabelColumn,
    PropertyColumn,
    QualifierColumn,
    ReferenceColumn,
    SitelinkColumn,
)
from ..grouping import GroupingConfiguration, ItemGroupingType, YearGroupingType
from ..grouping_link import LabelGroupingLink
from ..line import (
    ItemGrouping,
    NoGroupGrouping,
    TotalsGrouping,
    UnknownValueGrouping,
    YearGrouping,
)
from ..property_statistics import PropertyStatistics
from ..reference_check import (
    AllPropertiesReferenceCheck,
    AnyOfPropertiesReferenceCheck,
    GoodReferenceCheck,
    PropertyReferenceCheck,
)
from ..sparql_utils import QueryException, WdqsSparqlQueryEngine


class PropertyStatisticsTest(unittest.TestCase):
    def setUp(self):
        self.columns = [
            PropertyColumn(property="P1435"),
            PropertyColumn(property="P131"),
            QualifierColumn(property="P2929", qualifier="P462"),
            QualifierColumn(property="P1435", value="Q10387575", qualifier="P580"),
            LabelColumn(language="br"),
            DescriptionColumn(language="xy"),
            SitelinkColumn(project="brwiki"),
        ]
        self.grouping_configuration = GroupingConfiguration(
            predicate="wdt:P17", grouping_type=ItemGroupingType()
        )
        self.mock_sparql_query = create_autospec(WdqsSparqlQueryEngine, instance=True)
        self.stats = PropertyStatistics(
            columns=self.columns,
            grouping_configuration=self.grouping_configuration,
            selector_sparql="wdt:P31 wd:Q39715",
            property_threshold=10,
            sparql_query_engine=self.mock_sparql_query,
        )

    def assert_query_called(self, query):
        self.mock_sparql_query.select.assert_called_once_with(query)


class TestLabelColumn(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = LabelColumn("br")

    def test_simple(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{#language:br}}\n'
        self.assertEqual(result, expected)

    def test_get_key(self):
        result = self.column.get_key()
        self.assertEqual(result, "Lbr")

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        query = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715
  FILTER(EXISTS {
    ?entity rdfs:label ?lang_label.
    FILTER((LANG(?lang_label)) = 'br').
  })
}
"""
        self.assertEqual(result, query)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        query = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  ?entity wdt:P17 ?grouping .
  FILTER(EXISTS {
    ?entity rdfs:label ?lang_label.
    FILTER((LANG(?lang_label)) = 'br').
  })
}
GROUP BY ?grouping
HAVING (?count >= 10)
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, query)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        query = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  MINUS { ?entity wdt:P17 _:b28. }
  FILTER(EXISTS {
    ?entity rdfs:label ?lang_label.
    FILTER((LANG(?lang_label)) = 'br').
  })
}
"""
        self.assertEqual(result, query)


class TestDescriptionColumn(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = DescriptionColumn("br")

    def test_simple(self):
        result = self.column.make_column_header()
        expected = '! data-sort-type="number"|{{#language:br}}\n'
        self.assertEqual(result, expected)

    def test_get_key(self):
        result = self.column.get_key()
        self.assertEqual(result, "Dbr")

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        query = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715
  FILTER(EXISTS {
    ?entity schema:description ?lang_label.
    FILTER((LANG(?lang_label)) = 'br').
  })
}
"""
        self.assertEqual(result, query)

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        query = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  ?entity wdt:P17 ?grouping .
  FILTER(EXISTS {
    ?entity schema:description ?lang_label.
    FILTER((LANG(?lang_label)) = 'br').
  })
}
GROUP BY ?grouping
HAVING (?count >= 10)
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, query)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        query = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  MINUS { ?entity wdt:P17 _:b28. }
  FILTER(EXISTS {
    ?entity schema:description ?lang_label.
    FILTER((LANG(?lang_label)) = 'br').
  })
}
"""

        self.assertEqual(result, query)


class MakeStatsForNoGroupTest(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        patcher1 = patch(
            "integraality.property_statistics.PropertyStatistics.get_totals_no_grouping",
            autospec=True,
        )
        self.mock_get_totals_no_grouping = patcher1.start()
        self.addCleanup(patcher1.stop)
        self.mock_get_totals_no_grouping.return_value = 20
        self.mock_sparql_query.select.side_effect = [
            [{"count": "2"}],
            [{"count": "10"}],
            [{"count": "15"}],
            [{"count": "5"}],
            [{"count": "4"}],
            [{"count": "8"}],
            [{"count": "4"}],
        ]

    def test_make_stats_for_no_group(self):
        self.maxDiff = None
        result = self.stats.make_stats_for_no_group()
        expected = NoGroupGrouping(
            count=20, higher_grouping=self.grouping_configuration.higher_grouping
        )
        expected.cells = OrderedDict(
            [
                ("P1435", 2),
                ("P131", 10),
                ("P2929/P462", 15),
                ("P1435/Q10387575/P580", 5),
                ("Lbr", 4),
                ("Dxy", 8),
                ("brwiki", 4),
            ]
        )
        self.assertEqual(result, expected)
        self.mock_get_totals_no_grouping.assert_called_once_with(self.stats)
        self.assertEqual(self.mock_sparql_query.select.call_count, 7)

    def test_make_stats_for_no_group_with_higher_grouping(self):
        self.stats.grouping_configuration.higher_grouping = "wdt:P17/wdt:P298"
        result = self.stats.make_stats_for_no_group()
        expected = NoGroupGrouping(
            count=20, higher_grouping=self.stats.grouping_configuration.higher_grouping
        )
        expected.cells = OrderedDict(
            [
                ("P1435", 2),
                ("P131", 10),
                ("P2929/P462", 15),
                ("P1435/Q10387575/P580", 5),
                ("Lbr", 4),
                ("Dxy", 8),
                ("brwiki", 4),
            ]
        )
        self.assertEqual(result, expected)
        self.mock_get_totals_no_grouping.assert_called_once_with(self.stats)
        self.assertEqual(self.mock_sparql_query.select.call_count, 7)

    def test_make_stats_for_no_group_with_grouping_link(self):
        result = self.stats.make_stats_for_no_group()
        expected = NoGroupGrouping(
            count=20, higher_grouping=self.grouping_configuration.higher_grouping
        )
        expected.cells = OrderedDict(
            [
                ("P1435", 2),
                ("P131", 10),
                ("P2929/P462", 15),
                ("P1435/Q10387575/P580", 5),
                ("Lbr", 4),
                ("Dxy", 8),
                ("brwiki", 4),
            ]
        )
        self.assertEqual(result, expected)
        self.mock_get_totals_no_grouping.assert_called_once_with(self.stats)
        self.assertEqual(self.mock_sparql_query.select.call_count, 7)


class FindSpecialGroupingTest(unittest.TestCase):
    def test_no_grouping(self):
        result = PropertyStatistics._find_special_grouping("None")
        self.assertEqual(result, NoGroupGrouping)

    def test_totals(self):
        result = PropertyStatistics._find_special_grouping("")
        self.assertEqual(result, TotalsGrouping)

    def test_unknown_value(self):
        result = PropertyStatistics._find_special_grouping("UNKNOWN_VALUE")
        self.assertEqual(result, UnknownValueGrouping)

    def test_regular_grouping(self):
        result = PropertyStatistics._find_special_grouping("Q123")
        self.assertIsNone(result)


class GetQueryForItemsForPropertyPositive(PropertyStatisticsTest):
    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.stats.columns.get("P1435"), "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P1435 ?statement . OPTIONAL { ?statement ps:P1435 ?value }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_no_grouping(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.stats.columns.get("P1435"), NoGroupGrouping.MARKER
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    MINUS {
      ?entity wdt:P17 [] .
    }
    ?entity p:P1435 ?statement . OPTIONAL { ?statement ps:P1435 ?value }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_totals(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.stats.columns.get("P1435"), TotalsGrouping.MARKER
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity p:P1435 ?statement . OPTIONAL { ?statement ps:P1435 ?value }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_label(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.stats.columns.get("Lbr"), "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    FILTER(EXISTS {
      ?entity rdfs:label ?lang_label.
      FILTER((LANG(?lang_label)) = "br").
    })
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_unknown_value_grouping(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.stats.columns.get("P1435"), UnknownValueGrouping.MARKER
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 ?grouping.
    FILTER(STRSTARTS(STR(?grouping), 'http://www.wikidata.org/.well-known/genid/')).
    ?entity p:P1435 ?statement . OPTIONAL { ?statement ps:P1435 ?value }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_year_grouping(self):
        stats = PropertyStatistics(
            columns=self.columns,
            grouping_configuration=GroupingConfiguration(
                predicate="wdt:P571", grouping_type=YearGroupingType()
            ),
            selector_sparql="wdt:P31 wd:Q39715",
            grouping_type="year",
            sparql_query_engine=self.mock_sparql_query,
            property_threshold=10,
        )
        result = stats.get_query_for_items_for_property_positive(
            self.stats.columns.get("P1435"), 1892
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P571 ?date.
    BIND(YEAR(?date) as ?year).
    FILTER(?year = 1892).
    BIND(1892 AS ?grouping) .
    ?entity p:P1435 ?statement . OPTIONAL { ?statement ps:P1435 ?value }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_sitelink(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.stats.columns.get("brwiki"), "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?sitelink schema:about ?entity;
      schema:isPartOf <https://br.wikipedia.org/>;
      schema:name ?value.
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_qualifier(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.stats.columns.get("P2929/P462"), "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P2929 ?statement .
    { ?statement pq:P462 ?value . }
    UNION
    { ?statement a wdno:P462 . BIND("no value"@en AS ?valueLabel) }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_qualifier_with_value(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.stats.columns.get("P1435/Q10387575/P580"), "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P1435 ?statement .
    ?statement ps:P1435 wd:Q10387575 .
    { ?statement pq:P580 ?value . }
    UNION
    { ?statement a wdno:P580 . BIND("no value"@en AS ?valueLabel) }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_positive_qualifier_with_variable_value(
        self,
    ):
        self.stats.columns["P17/?grouping/P580"] = QualifierColumn(
            property="P17", value="?grouping", qualifier="P580"
        )
        result = self.stats.get_query_for_items_for_property_positive(
            self.stats.columns.get("P17/?grouping/P580"), "Q159"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q159 .
    BIND(wd:Q159 AS ?grouping) .
    ?entity p:P17 ?statement .
    ?statement ps:P17 ?grouping .
    { ?statement pq:P580 ?value . }
    UNION
    { ?statement a wdno:P580 . BIND("no value"@en AS ?valueLabel) }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)


class GetQueryForItemsForPropertyPositiveUnresolvedType(PropertyStatisticsTest):
    """Test that queries work when grouping_type is not yet resolved."""

    def test_resolves_type_before_accessing_line_type(self):
        self.mock_sparql_query.select.return_value = [
            {"datatype": "http://www.w3.org/2001/XMLSchema#dateTime"}
        ]
        config = GroupingConfiguration(
            predicate="wdt:P571",
            grouping_type=None,
            raw_explicit_groupings=None,
        )
        stats = PropertyStatistics(
            columns=self.columns,
            grouping_configuration=config,
            selector_sparql="wdt:P31 wd:Q39715",
            sparql_query_engine=self.mock_sparql_query,
            property_threshold=10,
        )
        self.mock_sparql_query.reset_mock()
        result = stats.get_query_for_items_for_property_positive(
            stats.columns.get("P1435"), 1893
        )
        self.assertIn("FILTER(?year = 1893)", result)


class TestReferenceColumn(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(property="P2923")
        self.stats.columns["P2923/S*"] = self.column

    def test_get_info_query(self):
        result = self.column.get_info_query(self.stats)
        query = """
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  ?entity wdt:P17 ?grouping .
  FILTER(EXISTS {
    ?entity p:P2923 [] .
    FILTER NOT EXISTS {
      ?entity p:P2923 ?_unreferenced_stmt .
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
        self.assertEqual(result, query)

    def test_get_info_no_grouping_query(self):
        result = self.column.get_info_no_grouping_query(self.stats)
        query = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?entity wdt:P31 wd:Q39715 .
  MINUS { ?entity wdt:P17 _:b28. }
  FILTER(EXISTS {
    ?entity p:P2923 [] .
    FILTER NOT EXISTS {
      ?entity p:P2923 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }
  })
}
"""
        self.assertEqual(result, query)

    def test_get_totals_query(self):
        result = self.column.get_totals_query(self.stats)
        query = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715
  FILTER(EXISTS {
    ?entity p:P2923 [] .
    FILTER NOT EXISTS {
      ?entity p:P2923 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }
  })
}
"""
        self.assertEqual(result, query)

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel ?refProperty ?refPropertyLabel ?refValue ?refValueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value ?refProperty ?refValue WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P2923 ?statement .
    ?statement ps:P2923 ?value .
    FILTER NOT EXISTS {
      ?entity p:P2923 ?_unreferenced_stmt .
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
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
  OPTIONAL {{
    ?refProperty rdfs:label ?refPropertylabelMUL.
    FILTER(lang(?refPropertylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?refProperty rdfs:label ?refPropertylabelEN.
    FILTER(lang(?refPropertylabelEN)='en')
  }}.
  BIND(COALESCE(?refPropertylabelEN, ?refPropertylabelMUL) AS ?refPropertyLabel).
  OPTIONAL {{
    ?refValue rdfs:label ?refValuelabelMUL.
    FILTER(lang(?refValuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?refValue rdfs:label ?refValuelabelEN.
    FILTER(lang(?refValuelabelEN)='en')
  }}.
  BIND(COALESCE(?refValuelabelEN, ?refValuelabelMUL) AS ?refValueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    OPTIONAL {
      ?entity p:P2923 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }
    OPTIONAL { ?entity p:P2923 ?_any_stmt . }
    FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
    OPTIONAL { ?entity p:P2923 ?_show_stmt . ?_show_stmt ps:P2923 ?value . }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_no_grouping(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.column, NoGroupGrouping.MARKER
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    MINUS {
      ?entity wdt:P17 [] .
    }
    OPTIONAL {
      ?entity p:P2923 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }
    OPTIONAL { ?entity p:P2923 ?_any_stmt . }
    FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
    OPTIONAL { ?entity p:P2923 ?_show_stmt . ?_show_stmt ps:P2923 ?value . }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)


class TestReferenceColumnSpecificProperty(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(
            property="P1435", reference_check=PropertyReferenceCheck("P248")
        )
        self.stats.columns["P1435/S248"] = self.column

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel ?refValue ?refValueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value ?refValue WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P1435 ?statement .
    ?statement ps:P1435 ?value .
    FILTER NOT EXISTS {
      ?entity p:P1435 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 []
      }
    }
    ?statement prov:wasDerivedFrom/pr:P248 ?refValue .
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
  OPTIONAL {{
    ?refValue rdfs:label ?refValuelabelMUL.
    FILTER(lang(?refValuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?refValue rdfs:label ?refValuelabelEN.
    FILTER(lang(?refValuelabelEN)='en')
  }}.
  BIND(COALESCE(?refValuelabelEN, ?refValuelabelMUL) AS ?refValueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    OPTIONAL {
      ?entity p:P1435 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 []
      }
    }
    OPTIONAL { ?entity p:P1435 ?_any_stmt . }
    FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
    OPTIONAL { ?entity p:P1435 ?_show_stmt . ?_show_stmt ps:P1435 ?value . }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)


class TestReferenceColumnSpecificPropertyValue(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(
            property="P1435",
            reference_check=PropertyReferenceCheck("P248", "Q809830"),
        )
        self.stats.columns["P1435/S248=Q809830"] = self.column

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P1435 ?statement .
    ?statement ps:P1435 ?value .
    FILTER NOT EXISTS {
      ?entity p:P1435 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 wd:Q809830
      }
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    OPTIONAL {
      ?entity p:P1435 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 wd:Q809830
      }
    }
    OPTIONAL { ?entity p:P1435 ?_any_stmt . }
    FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
    OPTIONAL { ?entity p:P1435 ?_show_stmt . ?_show_stmt ps:P1435 ?value . }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)


class TestReferenceColumnMultiProperty(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(
            property="P1435",
            reference_check=AnyOfPropertiesReferenceCheck(
                [("P248", None), ("P854", None)]
            ),
        )
        self.stats.columns["P1435/S248;S854"] = self.column

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel ?refValue ?refValueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value ?refValue WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P1435 ?statement .
    ?statement ps:P1435 ?value .
    FILTER NOT EXISTS {
      ?entity p:P1435 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
        { ?_ref pr:P248 [] } UNION { ?_ref pr:P854 [] }
      }
    }
    ?statement prov:wasDerivedFrom ?_refNode .
    OPTIONAL { ?_refNode pr:P248 ?_refNode_val_0 . }
    OPTIONAL { ?_refNode pr:P854 ?_refNode_val_1 . }
    BIND(COALESCE(?_refNode_val_0, ?_refNode_val_1) AS ?refValue)
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
  OPTIONAL {{
    ?refValue rdfs:label ?refValuelabelMUL.
    FILTER(lang(?refValuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?refValue rdfs:label ?refValuelabelEN.
    FILTER(lang(?refValuelabelEN)='en')
  }}.
  BIND(COALESCE(?refValuelabelEN, ?refValuelabelMUL) AS ?refValueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    OPTIONAL {
      ?entity p:P1435 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
        { ?_ref pr:P248 [] } UNION { ?_ref pr:P854 [] }
      }
    }
    OPTIONAL { ?entity p:P1435 ?_any_stmt . }
    FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
    OPTIONAL { ?entity p:P1435 ?_show_stmt . ?_show_stmt ps:P1435 ?value . }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)


class TestReferenceColumnAllProperties(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(
            property="P2929",
            reference_check=AllPropertiesReferenceCheck(
                [("P248", None), ("P304", None)]
            ),
        )
        self.stats.columns["P2929/S248+S304"] = self.column

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel ?ref_P248 ?ref_P248Label ?ref_P304 ?ref_P304Label WHERE {
  {
  SELECT DISTINCT ?entity ?value ?ref_P248 ?ref_P304 WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P2929 ?statement .
    ?statement ps:P2929 ?value .
    FILTER NOT EXISTS {
      ?entity p:P2929 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
        ?_ref pr:P248 [] .
        ?_ref pr:P304 [] .
      }
    }
    ?statement prov:wasDerivedFrom ?_refNode .
    ?_refNode pr:P248 ?ref_P248 .
    ?_refNode pr:P304 ?ref_P304 .
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
  OPTIONAL {{
    ?ref_P248 rdfs:label ?ref_P248labelMUL.
    FILTER(lang(?ref_P248labelMUL)='mul')
  }}.
  OPTIONAL {{
    ?ref_P248 rdfs:label ?ref_P248labelEN.
    FILTER(lang(?ref_P248labelEN)='en')
  }}.
  BIND(COALESCE(?ref_P248labelEN, ?ref_P248labelMUL) AS ?ref_P248Label).
  OPTIONAL {{
    ?ref_P304 rdfs:label ?ref_P304labelMUL.
    FILTER(lang(?ref_P304labelMUL)='mul')
  }}.
  OPTIONAL {{
    ?ref_P304 rdfs:label ?ref_P304labelEN.
    FILTER(lang(?ref_P304labelEN)='en')
  }}.
  BIND(COALESCE(?ref_P304labelEN, ?ref_P304labelMUL) AS ?ref_P304Label).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    OPTIONAL {
      ?entity p:P2929 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
        ?_ref pr:P248 [] .
        ?_ref pr:P304 [] .
      }
    }
    OPTIONAL { ?entity p:P2929 ?_any_stmt . }
    FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
    OPTIONAL { ?entity p:P2929 ?_show_stmt . ?_show_stmt ps:P2929 ?value . }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)


class TestReferenceColumnAllPropertiesValueScoped(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(
            property="P793",
            value="Q24410992",
            reference_check=AllPropertiesReferenceCheck(
                [("P813", None), ("P854", None)]
            ),
        )
        self.stats.columns["P793/Q24410992/S813+S854"] = self.column

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel ?ref_P813 ?ref_P813Label ?ref_P854 ?ref_P854Label WHERE {
  {
  SELECT DISTINCT ?entity ?value ?ref_P813 ?ref_P854 WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P793 ?statement .
    ?statement ps:P793 ?value .
    ?statement ps:P793 wd:Q24410992 .
    FILTER NOT EXISTS {
      ?entity p:P793 ?_unreferenced_stmt .
      ?_unreferenced_stmt ps:P793 wd:Q24410992 .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
        ?_ref pr:P813 [] .
        ?_ref pr:P854 [] .
      }
    }
    ?statement prov:wasDerivedFrom ?_refNode .
    ?_refNode pr:P813 ?ref_P813 .
    ?_refNode pr:P854 ?ref_P854 .
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
  OPTIONAL {{
    ?ref_P813 rdfs:label ?ref_P813labelMUL.
    FILTER(lang(?ref_P813labelMUL)='mul')
  }}.
  OPTIONAL {{
    ?ref_P813 rdfs:label ?ref_P813labelEN.
    FILTER(lang(?ref_P813labelEN)='en')
  }}.
  BIND(COALESCE(?ref_P813labelEN, ?ref_P813labelMUL) AS ?ref_P813Label).
  OPTIONAL {{
    ?ref_P854 rdfs:label ?ref_P854labelMUL.
    FILTER(lang(?ref_P854labelMUL)='mul')
  }}.
  OPTIONAL {{
    ?ref_P854 rdfs:label ?ref_P854labelEN.
    FILTER(lang(?ref_P854labelEN)='en')
  }}.
  BIND(COALESCE(?ref_P854labelEN, ?ref_P854labelMUL) AS ?ref_P854Label).
}
"""
        self.assertEqual(result, expected)


class TestReferenceColumnAllPropertiesWithValue(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(
            property="P2929",
            reference_check=AllPropertiesReferenceCheck(
                [("P248", "Q25198336"), ("P304", None)]
            ),
        )
        self.stats.columns["P2929/S248=Q25198336+S813"] = self.column

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel ?ref_P304 ?ref_P304Label WHERE {
  {
  SELECT DISTINCT ?entity ?value ?ref_P304 WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P2929 ?statement .
    ?statement ps:P2929 ?value .
    FILTER NOT EXISTS {
      ?entity p:P2929 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
        ?_ref pr:P248 wd:Q25198336 .
        ?_ref pr:P304 [] .
      }
    }
    ?statement prov:wasDerivedFrom ?_refNode .
    ?_refNode pr:P304 ?ref_P304 .
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
  OPTIONAL {{
    ?ref_P304 rdfs:label ?ref_P304labelMUL.
    FILTER(lang(?ref_P304labelMUL)='mul')
  }}.
  OPTIONAL {{
    ?ref_P304 rdfs:label ?ref_P304labelEN.
    FILTER(lang(?ref_P304labelEN)='en')
  }}.
  BIND(COALESCE(?ref_P304labelEN, ?ref_P304labelMUL) AS ?ref_P304Label).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    OPTIONAL {
      ?entity p:P2929 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
        ?_ref pr:P248 wd:Q25198336 .
        ?_ref pr:P304 [] .
      }
    }
    OPTIONAL { ?entity p:P2929 ?_any_stmt . }
    FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
    OPTIONAL { ?entity p:P2929 ?_show_stmt . ?_show_stmt ps:P2929 ?value . }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)


class TestReferenceColumnGood(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(
            property="P1435", reference_check=GoodReferenceCheck()
        )
        self.stats.columns["P1435/S!"] = self.column

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel ?refProperty ?refPropertyLabel ?refValue ?refValueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value ?refProperty ?refValue WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P1435 ?statement .
    ?statement ps:P1435 ?value .
    FILTER NOT EXISTS {
      ?entity p:P1435 ?_unreferenced_stmt .
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
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
  OPTIONAL {{
    ?refProperty rdfs:label ?refPropertylabelMUL.
    FILTER(lang(?refPropertylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?refProperty rdfs:label ?refPropertylabelEN.
    FILTER(lang(?refPropertylabelEN)='en')
  }}.
  BIND(COALESCE(?refPropertylabelEN, ?refPropertylabelMUL) AS ?refPropertyLabel).
  OPTIONAL {{
    ?refValue rdfs:label ?refValuelabelMUL.
    FILTER(lang(?refValuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?refValue rdfs:label ?refValuelabelEN.
    FILTER(lang(?refValuelabelEN)='en')
  }}.
  BIND(COALESCE(?refValuelabelEN, ?refValuelabelMUL) AS ?refValueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    OPTIONAL {
      ?entity p:P1435 ?_unreferenced_stmt .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom ?_ref .
        FILTER NOT EXISTS { ?_ref pr:P143 [] }
        FILTER NOT EXISTS { ?_ref pr:P3452 [] }
        FILTER NOT EXISTS { ?_ref pr:P887 [] }
      }
    }
    OPTIONAL { ?entity p:P1435 ?_any_stmt . }
    FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
    OPTIONAL { ?entity p:P1435 ?_show_stmt . ?_show_stmt ps:P1435 ?value . }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)


class TestReferenceColumnQualifierScoped(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.column = ReferenceColumn(property="P1435", qualifier="P580")
        self.stats.columns["P1435/P580/S*"] = self.column

    def test_get_query_for_items_for_property_positive(self):
        result = self.stats.get_query_for_items_for_property_positive(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel ?refProperty ?refPropertyLabel ?refValue ?refValueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value ?refProperty ?refValue WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    ?entity p:P1435 ?statement .
    ?statement ps:P1435 ?value .
    ?statement pq:P580 [] .
    FILTER NOT EXISTS {
      ?entity p:P1435 ?_unreferenced_stmt .
      ?_unreferenced_stmt pq:P580 [] .
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
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
  OPTIONAL {{
    ?refProperty rdfs:label ?refPropertylabelMUL.
    FILTER(lang(?refPropertylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?refProperty rdfs:label ?refPropertylabelEN.
    FILTER(lang(?refPropertylabelEN)='en')
  }}.
  BIND(COALESCE(?refPropertylabelEN, ?refPropertylabelMUL) AS ?refPropertyLabel).
  OPTIONAL {{
    ?refValue rdfs:label ?refValuelabelMUL.
    FILTER(lang(?refValuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?refValue rdfs:label ?refValuelabelEN.
    FILTER(lang(?refValuelabelEN)='en')
  }}.
  BIND(COALESCE(?refValuelabelEN, ?refValuelabelMUL) AS ?refValueLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.column, "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel ?value ?valueLabel WHERE {
  {
  SELECT DISTINCT ?entity ?value WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    OPTIONAL {
      ?entity p:P1435 ?_unreferenced_stmt .
      ?_unreferenced_stmt pq:P580 [] .
      FILTER NOT EXISTS {
        ?_unreferenced_stmt prov:wasDerivedFrom []
      }
    }
    OPTIONAL { ?entity p:P1435 ?_any_stmt .
      ?_any_stmt pq:P580 [] . }
    FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
    OPTIONAL { ?entity p:P1435 ?_show_stmt . ?_show_stmt ps:P1435 ?value . }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
  OPTIONAL {{
    ?value rdfs:label ?valuelabelMUL.
    FILTER(lang(?valuelabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?value rdfs:label ?valuelabelEN.
    FILTER(lang(?valuelabelEN)='en')
  }}.
  BIND(COALESCE(?valuelabelEN, ?valuelabelMUL) AS ?valueLabel).
}
"""
        self.assertEqual(result, expected)


class GetQueryForItemsForPropertyNegative(PropertyStatisticsTest):
    def test_get_query_for_items_for_property_negative(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.stats.columns.get("P1435"), "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    MINUS {
      {?entity a wdno:P1435 .} UNION
      {?entity wdt:P1435 ?statement .}
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_no_grouping(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.stats.columns.get("P1435"), NoGroupGrouping.MARKER
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    MINUS {
      ?entity wdt:P17 [] .
    }
    MINUS {
      {?entity a wdno:P1435 .} UNION
      {?entity wdt:P1435 ?statement .}
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_totals(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.stats.columns.get("P1435"), TotalsGrouping.MARKER
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    MINUS {
      {?entity a wdno:P1435 .} UNION
      {?entity wdt:P1435 ?statement .}
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_label(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.stats.columns.get("Lbr"), "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    MINUS {
      { ?entity rdfs:label ?lang_label.
      FILTER((LANG(?lang_label)) = "br") }
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_unknown_value_grouping(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.stats.columns.get("P1435"), UnknownValueGrouping.MARKER
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 ?grouping.
    FILTER(STRSTARTS(STR(?grouping), 'http://www.wikidata.org/.well-known/genid/')).
    MINUS {
      {?entity a wdno:P1435 .} UNION
      {?entity wdt:P1435 ?statement .}
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_year_grouping(self):
        stats = PropertyStatistics(
            columns=self.columns,
            grouping_configuration=GroupingConfiguration(
                predicate="wdt:P571", grouping_type=YearGroupingType()
            ),
            selector_sparql="wdt:P31 wd:Q39715",
            grouping_type="year",
            sparql_query_engine=self.mock_sparql_query,
            property_threshold=10,
        )
        result = stats.get_query_for_items_for_property_negative(
            self.stats.columns.get("P1435"), 1892
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P571 ?date.
    BIND(YEAR(?date) as ?year).
    FILTER(?year = 1892).
    BIND(1892 AS ?grouping) .
    MINUS {
      {?entity a wdno:P1435 .} UNION
      {?entity wdt:P1435 ?statement .}
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_sitelink(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.stats.columns.get("brwiki"), "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    MINUS {
      ?sitelink schema:about ?entity;
        schema:isPartOf <https://br.wikipedia.org/>.
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_qualifier(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.stats.columns.get("P2929/P462"), "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    MINUS {
      ?entity p:P2929 ?statement .
      { ?statement pq:P462 ?value . }
      UNION
      { ?statement a wdno:P462 . }
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_qualifier_with_value(self):
        result = self.stats.get_query_for_items_for_property_negative(
            self.stats.columns.get("P1435/Q10387575/P580"), "Q142"
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q142 .
    BIND(wd:Q142 AS ?grouping) .
    MINUS {
      ?entity p:P1435 ?statement .
      ?statement ps:P1435 wd:Q10387575 .
      { ?statement pq:P580 ?value . }
      UNION
      { ?statement a wdno:P580 . }
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)

    def test_get_query_for_items_for_property_negative_qualifier_with_variable_value(
        self,
    ):
        self.stats.columns["P17/?grouping/P580"] = QualifierColumn(
            property="P17", value="?grouping", qualifier="P580"
        )
        result = self.stats.get_query_for_items_for_property_negative(
            self.stats.columns.get("P17/?grouping/P580"), "Q159"
        )
        expected = """
SELECT ?entity ?entityLabel WHERE {
  {
  SELECT DISTINCT ?entity WHERE {
    ?entity wdt:P31 wd:Q39715 .
    ?entity wdt:P17 wd:Q159 .
    BIND(wd:Q159 AS ?grouping) .
    MINUS {
      ?entity p:P17 ?statement .
      ?statement ps:P17 ?grouping .
      { ?statement pq:P580 ?value . }
      UNION
      { ?statement a wdno:P580 . }
    }
  }
  }
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelMUL.
    FILTER(lang(?entitylabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?entity rdfs:label ?entitylabelEN.
    FILTER(lang(?entitylabelEN)='en')
  }}.
  BIND(COALESCE(?entitylabelEN, ?entitylabelMUL) AS ?entityLabel).
}
"""
        self.assertEqual(result, expected)


class GetCountFromSparqlTest(PropertyStatisticsTest):
    def test_return_count(self):
        self.mock_sparql_query.select.return_value = [{"count": "18"}]
        result = self.stats._get_count_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")
        self.assertEqual(result, 18)

    def test_return_None(self):
        self.mock_sparql_query.select.return_value = None
        with self.assertRaises(QueryException):
            self.stats._get_count_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")

    def test_return_timeout(self):
        self.mock_sparql_query.select.side_effect = QueryException("Error", "SELECT X")
        with self.assertRaises(QueryException):
            self.stats._get_count_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")


class GetGroupingCountsFromSparqlTest(PropertyStatisticsTest):
    def test_return_count(self):
        self.mock_sparql_query.select.return_value = [
            {"grouping": "http://www.wikidata.org/entity/Q1", "count": 10},
            {"grouping": "http://www.wikidata.org/entity/Q2", "count": 5},
        ]
        result = self.stats._get_grouping_counts_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")
        expected = OrderedDict([("Q1", 10), ("Q2", 5)])
        self.assertEqual(result, expected)

    def test_return_None(self):
        self.mock_sparql_query.select.return_value = None
        result = self.stats._get_grouping_counts_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")
        self.assertEqual(result, None)

    def test_return_timeout(self):
        self.mock_sparql_query.select.side_effect = QueryException("Error", "SELECT X")
        with self.assertRaises(QueryException):
            self.stats._get_grouping_counts_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")

    def test_return_count_with_unknown(self):
        self.mock_sparql_query.select.return_value = [
            {"grouping": "http://www.wikidata.org/entity/Q1", "count": 10},
            {"grouping": "http://www.wikidata.org/entity/Q2", "count": 5},
            {
                "grouping": "http://www.wikidata.org/.well-known/genid/6ab4c2d7cb4ac72721335af5b8ba09c7",
                "count": 2,
            },
            {
                "grouping": "http://www.wikidata.org/.well-known/genid/1469448a291c6fbe5df8306cb52ef18b",
                "count": 1,
            },
        ]
        result = self.stats._get_grouping_counts_from_sparql("SELECT X")
        self.assert_query_called("SELECT X")
        expected = OrderedDict([("Q1", 10), ("Q2", 5), ("UNKNOWN_VALUE", 3)])
        self.assertEqual(result, expected)


class SparqlCountTest(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.mock_sparql_query.select.return_value = [{"count": "18"}]

    def test_get_totals_no_grouping(self):
        result = self.stats.get_totals_no_grouping()
        query = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715
  MINUS { ?entity wdt:P17 _:b28. }
}
"""
        self.assert_query_called(query)
        self.assertEqual(result, 18)

    def test_get_totals(self):
        result = self.stats.get_totals()
        query = """
SELECT (COUNT(*) as ?count) WHERE {
  ?entity wdt:P31 wd:Q39715
}
"""
        self.assert_query_called(query)
        self.assertEqual(result, 18)


class GetGroupingInformationTest(PropertyStatisticsTest):
    def test_get_grouping_information(self):
        self.mock_sparql_query.select.return_value = [
            {"grouping": "http://www.wikidata.org/entity/Q142", "count": "10"},
            {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "6"},
            {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "6"},
        ]
        expected = {
            "Q142": ItemGrouping(title="Q142", count=10),
            "Q5087901": ItemGrouping(title="Q5087901", count=6),
            "Q623333": ItemGrouping(title="Q623333", count=6),
        }
        query = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q39715 .
      ?entity wdt:P17 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        result = self.stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_with_grouping_threshold(self):
        self.mock_sparql_query.select.return_value = [
            {"grouping": "http://www.wikidata.org/entity/Q142", "count": "10"},
            {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "6"},
            {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "6"},
        ]
        expected = {
            "Q142": ItemGrouping(title="Q142", count=10),
            "Q5087901": ItemGrouping(title="Q5087901", count=6),
            "Q623333": ItemGrouping(title="Q623333", count=6),
        }
        self.stats.grouping_configuration.grouping_threshold = 5
        query = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q39715 .
      ?entity wdt:P17 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 5)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        result = self.stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_with_higher_grouping(self):
        self.mock_sparql_query.select.return_value = [
            {
                "grouping": "http://www.wikidata.org/entity/Q142",
                "higher_grouping": "NZL",
                "count": "10",
            },
            {
                "grouping": "http://www.wikidata.org/entity/Q5087901",
                "higher_grouping": "USA",
                "count": "6",
            },
            {
                "grouping": "http://www.wikidata.org/entity/Q623333",
                "higher_grouping": "USA",
                "count": "6",
            },
        ]
        expected = {
            "Q142": ItemGrouping(title="Q142", count=10, higher_grouping="NZL"),
            "Q5087901": ItemGrouping(title="Q5087901", count=6, higher_grouping="USA"),
            "Q623333": ItemGrouping(title="Q623333", count=6, higher_grouping="USA"),
        }
        self.stats.grouping_configuration.higher_grouping = "wdt:P17/wdt:P298"
        query = """
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q39715 .
      ?entity wdt:P17 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
  OPTIONAL { ?grouping wdt:P17/wdt:P298 ?_higher_grouping }.
}
GROUP BY ?grouping ?count
ORDER BY DESC(?count)
LIMIT 1000
"""
        result = self.stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_empty_result(self):
        self.mock_sparql_query.select.return_value = None
        query = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q39715 .
      ?entity wdt:P17 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        with self.assertRaises(QueryException):
            self.stats.get_grouping_information()
        self.assert_query_called(query)

    def test_get_grouping_information_timeout(self):
        self.mock_sparql_query.select.side_effect = QueryException("Error", "SELECT X")
        query = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q39715 .
      ?entity wdt:P17 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        with self.assertRaises(QueryException):
            self.stats.get_grouping_information()
        self.assert_query_called(query)

    def test_get_grouping_information_timeout_bis(self):
        self.mock_sparql_query.select.side_effect = QueryException("Error", "SELECT X")
        query = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q39715 .
      ?entity wdt:P17 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        with self.assertRaises(QueryException):
            self.stats.get_grouping_information()
        self.assert_query_called(query)

    def test_get_grouping_information_unknown_value(self):
        self.mock_sparql_query.select.return_value = [
            {"grouping": "http://www.wikidata.org/entity/Q142", "count": "10"},
            {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "6"},
            {
                "grouping": "http://www.wikidata.org/.well-known/genid/6ab4c2d7cb4ac72721335af5b8ba09c7",
                "count": "2",
            },
            {
                "grouping": "http://www.wikidata.org/.well-known/genid/1469448a291c6fbe5df8306cb52ef18b",
                "count": "1",
            },
        ]
        expected = {
            "Q142": ItemGrouping(title="Q142", count=10),
            "Q5087901": ItemGrouping(title="Q5087901", count=6),
            "UNKNOWN_VALUE": UnknownValueGrouping(count=3),
        }
        query = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q39715 .
      ?entity wdt:P17 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        result = self.stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_year(self):
        stats = PropertyStatistics(
            columns=self.columns,
            grouping_configuration=GroupingConfiguration(
                predicate="wdt:P571", grouping_type=YearGroupingType()
            ),
            selector_sparql="wdt:P31 wd:Q39715",
            grouping_type="year",
            sparql_query_engine=self.mock_sparql_query,
            property_threshold=10,
        )

        self.mock_sparql_query.select.return_value = [
            {"grouping": "2001", "count": "10"},
            {"grouping": "2002", "count": "6"},
        ]
        expected = {
            "2001": YearGrouping(title="2001", count=10),
            "2002": YearGrouping(title="2002", count=6),
        }
        query = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q39715 .
      ?entity wdt:P571 ?date .
      BIND(YEAR(?date) as ?grouping) .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        result = stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_year_unknown_value(self):
        stats = PropertyStatistics(
            columns=self.columns,
            grouping_configuration=GroupingConfiguration(
                predicate="wdt:P571", grouping_type=YearGroupingType()
            ),
            selector_sparql="wdt:P31 wd:Q39715",
            grouping_type="year",
            sparql_query_engine=self.mock_sparql_query,
            property_threshold=10,
        )

        self.mock_sparql_query.select.return_value = [
            {"grouping": "2001", "count": "10"},
            {"grouping": "2002", "count": "6"},
            {"grouping": "", "count": "4"},
        ]
        expected = {
            "2001": YearGrouping(title="2001", count=10),
            "2002": YearGrouping(title="2002", count=6),
            "UNKNOWN_VALUE": UnknownValueGrouping(count=4),
        }
        query = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q39715 .
      ?entity wdt:P571 ?date .
      BIND(YEAR(?date) as ?grouping) .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        result = stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)

    def test_get_grouping_information_with_grouping_link(self):
        self.mock_sparql_query.select.return_value = [
            {
                "grouping": "http://www.wikidata.org/entity/Q142",
                "grouping_link_value": "A",
                "count": "10",
            },
            {
                "grouping": "http://www.wikidata.org/entity/Q5087901",
                "grouping_link_value": "B",
                "count": "6",
            },
            {
                "grouping": "http://www.wikidata.org/entity/Q623333",
                "grouping_link_value": "C",
                "count": "6",
            },
        ]
        expected = {
            "Q142": ItemGrouping(title="Q142", grouping_link="Foo/A", count=10),
            "Q5087901": ItemGrouping(title="Q5087901", grouping_link="Foo/B", count=6),
            "Q623333": ItemGrouping(title="Q623333", grouping_link="Foo/C", count=6),
        }
        query = """
SELECT ?grouping ?grouping_link_value ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q39715 .
      ?entity wdt:P17 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
  OPTIONAL {{
    ?grouping rdfs:label ?groupinglabelMUL.
    FILTER(lang(?groupinglabelMUL)='mul')
  }}.
  OPTIONAL {{
    ?grouping rdfs:label ?groupinglabelEN.
    FILTER(lang(?groupinglabelEN)='en')
  }}.
  BIND(COALESCE(?groupinglabelEN, ?groupinglabelMUL) AS ?grouping_link_value).
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.stats.grouping_configuration.grouping_link_type = LabelGroupingLink(
            template="Foo/{Len}"
        )
        result = self.stats.get_grouping_information()
        self.assert_query_called(query)
        self.assertEqual(result, expected)


class MakeTotalsTest(PropertyStatisticsTest):
    def setUp(self):
        super().setUp()
        self.mock_sparql_query.select.side_effect = [
            [{"count": "120"}],
            [{"count": "30"}],
            [{"count": "80"}],
            [{"count": "10"}],
            [{"count": "12"}],
            [{"count": "24"}],
            [{"count": "36"}],
            [{"count": "24"}],
        ]

    def test_make_totals(self):
        result = self.stats.make_totals()
        expected = TotalsGrouping(
            count=120,
            title="",
            higher_grouping=self.grouping_configuration.higher_grouping,
        )
        expected.cells = OrderedDict(
            [
                ("P1435", 30),
                ("P131", 80),
                ("P2929/P462", 10),
                ("P1435/Q10387575/P580", 12),
                ("Lbr", 24),
                ("Dxy", 36),
                ("brwiki", 24),
            ]
        )
        self.assertEqual(result, expected)

    def test_make_totals_with_higher_grouping(self):
        self.stats.grouping_configuration.higher_grouping = "wdt:P17/wdt:P298"
        result = self.stats.make_totals()
        expected = TotalsGrouping(
            count=120,
            title="",
            higher_grouping=self.stats.grouping_configuration.higher_grouping,
        )
        expected.cells = OrderedDict(
            [
                ("P1435", 30),
                ("P131", 80),
                ("P2929/P462", 10),
                ("P1435/Q10387575/P580", 12),
                ("Lbr", 24),
                ("Dxy", 36),
                ("brwiki", 24),
            ]
        )
        self.assertEqual(result, expected)

    def test_make_totals_with_grouping_link(self):
        result = self.stats.make_totals()
        expected = TotalsGrouping(
            count=120,
            title="",
            higher_grouping=self.grouping_configuration.higher_grouping,
        )
        expected.cells = OrderedDict(
            [
                ("P1435", 30),
                ("P131", 80),
                ("P2929/P462", 10),
                ("P1435/Q10387575/P580", 12),
                ("Lbr", 24),
                ("Dxy", 36),
                ("brwiki", 24),
            ]
        )
        self.assertEqual(result, expected)


class PopulateGroupingsTest(PropertyStatisticsTest):
    def test_populate_groupings_empty(self):
        result = self.stats.populate_groupings(None)
        self.assertEqual(result, None)

    def test_populate_groupings_no_columns(self):
        groupings = {
            "Q142": ItemGrouping(title="Q142", count=10),
            "Q5087901": ItemGrouping(title="Q5087901", count=6),
            "Q623333": ItemGrouping(title="Q623333", count=6),
        }
        result = self.stats.populate_groupings(groupings)
        self.assertEqual(result, groupings)

    def test_populate_groupings_with_columns(self):
        groupings = {
            "Q142": ItemGrouping(title="Q142", count=10),
            "Q5087901": ItemGrouping(title="Q5087901", count=6),
            "Q623333": ItemGrouping(title="Q623333", count=6),
        }
        self.mock_sparql_query.select.side_effect = [
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "1"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "2"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "3"},
                {"grouping": "http://www.wikidata.org/entity/Q11953090", "count": "4"},
            ],
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "5"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "6"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "7"},
                {"grouping": "http://www.wikidata.org/entity/Q11953090", "count": "8"},
            ],
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "9"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "10"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "11"},
                {"grouping": "http://www.wikidata.org/entity/Q11953090", "count": "12"},
            ],
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "13"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "14"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "15"},
                {"grouping": "http://www.wikidata.org/entity/Q11953090", "count": "16"},
            ],
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "17"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "18"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "19"},
                {"grouping": "http://www.wikidata.org/entity/Q11953090", "count": "20"},
            ],
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "21"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "22"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "23"},
                {"grouping": "http://www.wikidata.org/entity/Q11953090", "count": "24"},
            ],
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "25"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "26"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "27"},
                {"grouping": "http://www.wikidata.org/entity/Q11953090", "count": "28"},
            ],
        ]
        result = self.stats.populate_groupings(groupings)
        expected = {
            "Q142": ItemGrouping(
                title="Q142",
                count=10,
                cells=OrderedDict(
                    [
                        ("P1435", 1),
                        ("P131", 5),
                        ("P2929/P462", 9),
                        ("P1435/Q10387575/P580", 13),
                        ("Lbr", 17),
                        ("Dxy", 21),
                        ("brwiki", 25),
                    ]
                ),
            ),
            "Q5087901": ItemGrouping(
                title="Q5087901",
                count=6,
                cells=OrderedDict(
                    [
                        ("P1435", 2),
                        ("P131", 6),
                        ("P2929/P462", 10),
                        ("P1435/Q10387575/P580", 14),
                        ("Lbr", 18),
                        ("Dxy", 22),
                        ("brwiki", 26),
                    ]
                ),
            ),
            "Q623333": ItemGrouping(
                title="Q623333",
                count=6,
                cells=OrderedDict(
                    [
                        ("P1435", 3),
                        ("P131", 7),
                        ("P2929/P462", 11),
                        ("P1435/Q10387575/P580", 15),
                        ("Lbr", 19),
                        ("Dxy", 23),
                        ("brwiki", 27),
                    ]
                ),
            ),
        }
        self.assertEqual(result, expected)

    def test_populate_groupings_with_columns_one_empty(self):
        groupings = {
            "Q142": ItemGrouping(title="Q142", count=10),
            "Q5087901": ItemGrouping(title="Q5087901", count=6),
            "Q623333": ItemGrouping(title="Q623333", count=6),
        }
        self.mock_sparql_query.select.side_effect = [
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "1"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "2"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "3"},
            ],
            None,
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "9"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "10"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "11"},
            ],
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "13"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "14"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "15"},
            ],
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "17"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "18"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "19"},
            ],
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "21"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "22"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "23"},
            ],
            [
                {"grouping": "http://www.wikidata.org/entity/Q142", "count": "24"},
                {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "25"},
                {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "26"},
            ],
        ]
        result = self.stats.populate_groupings(groupings)
        expected = {
            "Q142": ItemGrouping(
                title="Q142",
                count=10,
                cells=OrderedDict(
                    [
                        ("P1435", 1),
                        ("P2929/P462", 9),
                        ("P1435/Q10387575/P580", 13),
                        ("Lbr", 17),
                        ("Dxy", 21),
                        ("brwiki", 24),
                    ]
                ),
            ),
            "Q5087901": ItemGrouping(
                title="Q5087901",
                count=6,
                cells=OrderedDict(
                    [
                        ("P1435", 2),
                        ("P2929/P462", 10),
                        ("P1435/Q10387575/P580", 14),
                        ("Lbr", 18),
                        ("Dxy", 22),
                        ("brwiki", 25),
                    ]
                ),
            ),
            "Q623333": ItemGrouping(
                title="Q623333",
                count=6,
                cells=OrderedDict(
                    [
                        ("P1435", 3),
                        ("P2929/P462", 11),
                        ("P1435/Q10387575/P580", 15),
                        ("Lbr", 19),
                        ("Dxy", 23),
                        ("brwiki", 26),
                    ]
                ),
            ),
        }
        self.assertEqual(result, expected)


class RetrieveDataTest(PropertyStatisticsTest):
    def test_retrieve_data_empty(self):
        result = self.stats.retrieve_data()
        expected = {}
        self.assertEqual(result, expected)

    def test_retrieve_data(self):
        self.mock_sparql_query.select.return_value = [
            {"grouping": "http://www.wikidata.org/entity/Q142", "count": "10"},
            {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "6"},
            {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "6"},
        ]
        result = self.stats.retrieve_data()
        expected = {
            "Q142": ItemGrouping(
                title="Q142",
                count=10,
                cells=OrderedDict(
                    [
                        ("P1435", 10),
                        ("P131", 10),
                        ("P2929/P462", 10),
                        ("P1435/Q10387575/P580", 10),
                        ("Lbr", 10),
                        ("Dxy", 10),
                        ("brwiki", 10),
                    ]
                ),
            ),
            "Q5087901": ItemGrouping(
                title="Q5087901",
                count=6,
                cells=OrderedDict(
                    [
                        ("P1435", 6),
                        ("P131", 6),
                        ("P2929/P462", 6),
                        ("P1435/Q10387575/P580", 6),
                        ("Lbr", 6),
                        ("Dxy", 6),
                        ("brwiki", 6),
                    ]
                ),
            ),
            "Q623333": ItemGrouping(
                title="Q623333",
                count=6,
                cells=OrderedDict(
                    [
                        ("P1435", 6),
                        ("P131", 6),
                        ("P2929/P462", 6),
                        ("P1435/Q10387575/P580", 6),
                        ("Lbr", 6),
                        ("Dxy", 6),
                        ("brwiki", 6),
                    ]
                ),
            ),
        }
        self.assertEqual(result, expected)


class ProcessDataTest(PropertyStatisticsTest):
    def test_process_data_empty(self):
        result = self.stats.process_data({})
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="7"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P1435}}\n'
            '! data-sort-type="number"|{{Property|P131}}\n'
            '! data-sort-type="number"|{{Property|P462}}\n'
            '! data-sort-type="number"|{{Property|P580}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            '! data-sort-type="number"|{{#language:xy}}\n'
            '! data-sort-type="number"|{{Q|Q846871}}\n'
            '|- class="sortbottom"\n'
            "| '''Totals''' <small>(all items)</small>\n"
            "| 1 \n"
            "| {{Integraality cell|100.0|1|column=P1435|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=P131|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=P2929/P462|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=P1435/Q10387575/P580|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=Lbr|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=Dxy|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=brwiki|grouping=}}\n"
            "|}\n"
        )
        self.assertEqual(result, expected)

    def test_process_data(self):
        grouping_data = {
            "Q142": ItemGrouping(
                title="Q142",
                count=10,
                cells=OrderedDict(
                    [
                        ("P1435", 10),
                        ("P131", 8),
                        ("P2929/P462", 2),
                        ("P1435/Q10387575/P580", 7),
                        ("Lbr", 1),
                        ("Dxy", 2),
                        ("brwiki", 1),
                    ]
                ),
            ),
            "Q5087901": ItemGrouping(
                title="Q5087901",
                count=6,
                cells=OrderedDict(
                    [
                        ("P1435", 6),
                        ("P131", 0),
                        ("P2929/P462", 0),
                        ("P1435/Q10387575/P580", 0),
                        ("Lbr", 0),
                        ("Dxy", 0),
                        ("brwiki", 0),
                    ]
                ),
            ),
        }

        result = self.stats.process_data(grouping_data)
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="7"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P1435}}\n'
            '! data-sort-type="number"|{{Property|P131}}\n'
            '! data-sort-type="number"|{{Property|P462}}\n'
            '! data-sort-type="number"|{{Property|P580}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            '! data-sort-type="number"|{{#language:xy}}\n'
            '! data-sort-type="number"|{{Q|Q846871}}\n'
            "|-\n"
            "| {{Q|Q142}}\n"
            "| 10 \n"
            "| {{Integraality cell|100.0|10|column=P1435|grouping=Q142}}\n"
            "| {{Integraality cell|80.0|8|column=P131|grouping=Q142}}\n"
            "| {{Integraality cell|20.0|2|column=P2929/P462|grouping=Q142}}\n"
            "| {{Integraality cell|70.0|7|column=P1435/Q10387575/P580|grouping=Q142}}\n"
            "| {{Integraality cell|10.0|1|column=Lbr|grouping=Q142}}\n"
            "| {{Integraality cell|20.0|2|column=Dxy|grouping=Q142}}\n"
            "| {{Integraality cell|10.0|1|column=brwiki|grouping=Q142}}\n"
            "|-\n"
            "| {{Q|Q5087901}}\n"
            "| 6 \n"
            "| {{Integraality cell|100.0|6|column=P1435|grouping=Q5087901}}\n"
            "| {{Integraality cell|0|0|column=P131|grouping=Q5087901}}\n"
            "| {{Integraality cell|0|0|column=P2929/P462|grouping=Q5087901}}\n"
            "| {{Integraality cell|0|0|column=P1435/Q10387575/P580|grouping=Q5087901}}\n"
            "| {{Integraality cell|0|0|column=Lbr|grouping=Q5087901}}\n"
            "| {{Integraality cell|0|0|column=Dxy|grouping=Q5087901}}\n"
            "| {{Integraality cell|0|0|column=brwiki|grouping=Q5087901}}\n"
            '|- class="sortbottom"\n'
            "| '''Totals''' <small>(all items)</small>\n"
            "| 1 \n"
            "| {{Integraality cell|100.0|1|column=P1435|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=P131|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=P2929/P462|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=P1435/Q10387575/P580|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=Lbr|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=Dxy|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=brwiki|grouping=}}\n"
            "|}\n"
        )

        self.assertEqual(result, expected)

    def test_process_data_year_grouping(self):
        grouping_data = {
            "2001": YearGrouping(
                title="2001",
                count=10,
                cells=OrderedDict(
                    [
                        ("P1435", 10),
                        ("P131", 8),
                        ("P2929/P462", 2),
                        ("P1435/Q10387575/P580", 7),
                        ("Lbr", 1),
                        ("Dxy", 2),
                        ("brwiki", 1),
                    ]
                ),
            ),
            "2018": YearGrouping(
                title="2018",
                count=6,
                cells=OrderedDict(
                    [
                        ("P1435", 6),
                        ("P131", 0),
                        ("P2929/P462", 0),
                        ("P1435/Q10387575/P580", 0),
                        ("Lbr", 0),
                        ("Dxy", 0),
                        ("brwiki", 0),
                    ]
                ),
            ),
        }

        result = self.stats.process_data(grouping_data)
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="7"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P1435}}\n'
            '! data-sort-type="number"|{{Property|P131}}\n'
            '! data-sort-type="number"|{{Property|P462}}\n'
            '! data-sort-type="number"|{{Property|P580}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            '! data-sort-type="number"|{{#language:xy}}\n'
            '! data-sort-type="number"|{{Q|Q846871}}\n'
            "|-\n"
            "| 2001\n"
            "| 10 \n"
            "| {{Integraality cell|100.0|10|column=P1435|grouping=2001}}\n"
            "| {{Integraality cell|80.0|8|column=P131|grouping=2001}}\n"
            "| {{Integraality cell|20.0|2|column=P2929/P462|grouping=2001}}\n"
            "| {{Integraality cell|70.0|7|column=P1435/Q10387575/P580|grouping=2001}}\n"
            "| {{Integraality cell|10.0|1|column=Lbr|grouping=2001}}\n"
            "| {{Integraality cell|20.0|2|column=Dxy|grouping=2001}}\n"
            "| {{Integraality cell|10.0|1|column=brwiki|grouping=2001}}\n"
            "|-\n"
            "| 2018\n"
            "| 6 \n"
            "| {{Integraality cell|100.0|6|column=P1435|grouping=2018}}\n"
            "| {{Integraality cell|0|0|column=P131|grouping=2018}}\n"
            "| {{Integraality cell|0|0|column=P2929/P462|grouping=2018}}\n"
            "| {{Integraality cell|0|0|column=P1435/Q10387575/P580|grouping=2018}}\n"
            "| {{Integraality cell|0|0|column=Lbr|grouping=2018}}\n"
            "| {{Integraality cell|0|0|column=Dxy|grouping=2018}}\n"
            "| {{Integraality cell|0|0|column=brwiki|grouping=2018}}\n"
            '|- class="sortbottom"\n'
            "| '''Totals''' <small>(all items)</small>\n"
            "| 1 \n"
            "| {{Integraality cell|100.0|1|column=P1435|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=P131|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=P2929/P462|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=P1435/Q10387575/P580|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=Lbr|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=Dxy|grouping=}}\n"
            "| {{Integraality cell|100.0|1|column=brwiki|grouping=}}\n"
            "|}\n"
        )

        self.assertEqual(result, expected)

    def test_prepare_report_groupings_no_totals(self):
        self.stats.row_totals = False
        result = self.stats.prepare_report_groupings({})
        self.assertFalse(
            any(isinstance(g, TotalsGrouping) for g in result),
            "TotalsGrouping should not be present when row_totals=False",
        )

    def test_prepare_report_groupings_with_totals(self):
        self.stats.row_totals = True
        result = self.stats.prepare_report_groupings({})
        self.assertTrue(
            any(isinstance(g, TotalsGrouping) for g in result),
            "TotalsGrouping should be present when row_totals=True",
        )


class RetrieveAndProcessDataTest(PropertyStatisticsTest):
    def test_retrieve_and_process_data(self):
        self.mock_sparql_query.select.return_value = [
            {"grouping": "http://www.wikidata.org/entity/Q142", "count": "10"},
            {"grouping": "http://www.wikidata.org/entity/Q5087901", "count": "6"},
            {"grouping": "http://www.wikidata.org/entity/Q623333", "count": "6"},
        ]
        result = self.stats.retrieve_and_process_data()
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="7"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P1435}}\n'
            '! data-sort-type="number"|{{Property|P131}}\n'
            '! data-sort-type="number"|{{Property|P462}}\n'
            '! data-sort-type="number"|{{Property|P580}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            '! data-sort-type="number"|{{#language:xy}}\n'
            '! data-sort-type="number"|{{Q|Q846871}}\n'
            "|-\n"
            "| {{Q|Q142}}\n"
            "| 10 \n"
            "| {{Integraality cell|100.0|10|column=P1435|grouping=Q142}}\n"
            "| {{Integraality cell|100.0|10|column=P131|grouping=Q142}}\n"
            "| {{Integraality cell|100.0|10|column=P2929/P462|grouping=Q142}}\n"
            "| {{Integraality cell|100.0|10|column=P1435/Q10387575/P580|grouping=Q142}}\n"
            "| {{Integraality cell|100.0|10|column=Lbr|grouping=Q142}}\n"
            "| {{Integraality cell|100.0|10|column=Dxy|grouping=Q142}}\n"
            "| {{Integraality cell|100.0|10|column=brwiki|grouping=Q142}}\n"
            "|-\n"
            "| {{Q|Q5087901}}\n"
            "| 6 \n"
            "| {{Integraality cell|100.0|6|column=P1435|grouping=Q5087901}}\n"
            "| {{Integraality cell|100.0|6|column=P131|grouping=Q5087901}}\n"
            "| {{Integraality cell|100.0|6|column=P2929/P462|grouping=Q5087901}}\n"
            "| {{Integraality cell|100.0|6|column=P1435/Q10387575/P580|grouping=Q5087901}}\n"
            "| {{Integraality cell|100.0|6|column=Lbr|grouping=Q5087901}}\n"
            "| {{Integraality cell|100.0|6|column=Dxy|grouping=Q5087901}}\n"
            "| {{Integraality cell|100.0|6|column=brwiki|grouping=Q5087901}}\n"
            "|-\n"
            "| {{Q|Q623333}}\n"
            "| 6 \n"
            "| {{Integraality cell|100.0|6|column=P1435|grouping=Q623333}}\n"
            "| {{Integraality cell|100.0|6|column=P131|grouping=Q623333}}\n"
            "| {{Integraality cell|100.0|6|column=P2929/P462|grouping=Q623333}}\n"
            "| {{Integraality cell|100.0|6|column=P1435/Q10387575/P580|grouping=Q623333}}\n"
            "| {{Integraality cell|100.0|6|column=Lbr|grouping=Q623333}}\n"
            "| {{Integraality cell|100.0|6|column=Dxy|grouping=Q623333}}\n"
            "| {{Integraality cell|100.0|6|column=brwiki|grouping=Q623333}}\n"
            '|- class="sortbottom"\n'
            "| '''Totals''' <small>(all items)</small>\n"
            "| 10 \n"
            "| {{Integraality cell|100.0|10|column=P1435|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=P131|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=P2929/P462|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=P1435/Q10387575/P580|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=Lbr|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=Dxy|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=brwiki|grouping=}}\n"
            "|}\n"
        )
        self.assertEqual(result, expected)

    def test_retrieve_and_process_data_year_grouping(self):
        self.grouping_configuration = GroupingConfiguration(
            predicate="wdt:P17", grouping_type=YearGroupingType()
        )
        self.stats = PropertyStatistics(
            columns=self.columns,
            grouping_configuration=self.grouping_configuration,
            selector_sparql="wdt:P31 wd:Q39715",
            property_threshold=10,
            sparql_query_engine=self.mock_sparql_query,
        )

        self.mock_sparql_query.select.return_value = [
            {"grouping": "2001", "count": "10"},
            {"grouping": "2012", "count": "6"},
            {"grouping": "2023", "count": "6"},
        ]
        result = self.stats.retrieve_and_process_data()
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="7"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P1435}}\n'
            '! data-sort-type="number"|{{Property|P131}}\n'
            '! data-sort-type="number"|{{Property|P462}}\n'
            '! data-sort-type="number"|{{Property|P580}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            '! data-sort-type="number"|{{#language:xy}}\n'
            '! data-sort-type="number"|{{Q|Q846871}}\n'
            "|-\n"
            "| 2001\n"
            "| 10 \n"
            "| {{Integraality cell|100.0|10|column=P1435|grouping=2001}}\n"
            "| {{Integraality cell|100.0|10|column=P131|grouping=2001}}\n"
            "| {{Integraality cell|100.0|10|column=P2929/P462|grouping=2001}}\n"
            "| {{Integraality cell|100.0|10|column=P1435/Q10387575/P580|grouping=2001}}\n"
            "| {{Integraality cell|100.0|10|column=Lbr|grouping=2001}}\n"
            "| {{Integraality cell|100.0|10|column=Dxy|grouping=2001}}\n"
            "| {{Integraality cell|100.0|10|column=brwiki|grouping=2001}}\n"
            "|-\n"
            "| 2012\n"
            "| 6 \n"
            "| {{Integraality cell|100.0|6|column=P1435|grouping=2012}}\n"
            "| {{Integraality cell|100.0|6|column=P131|grouping=2012}}\n"
            "| {{Integraality cell|100.0|6|column=P2929/P462|grouping=2012}}\n"
            "| {{Integraality cell|100.0|6|column=P1435/Q10387575/P580|grouping=2012}}\n"
            "| {{Integraality cell|100.0|6|column=Lbr|grouping=2012}}\n"
            "| {{Integraality cell|100.0|6|column=Dxy|grouping=2012}}\n"
            "| {{Integraality cell|100.0|6|column=brwiki|grouping=2012}}\n"
            "|-\n"
            "| 2023\n"
            "| 6 \n"
            "| {{Integraality cell|100.0|6|column=P1435|grouping=2023}}\n"
            "| {{Integraality cell|100.0|6|column=P131|grouping=2023}}\n"
            "| {{Integraality cell|100.0|6|column=P2929/P462|grouping=2023}}\n"
            "| {{Integraality cell|100.0|6|column=P1435/Q10387575/P580|grouping=2023}}\n"
            "| {{Integraality cell|100.0|6|column=Lbr|grouping=2023}}\n"
            "| {{Integraality cell|100.0|6|column=Dxy|grouping=2023}}\n"
            "| {{Integraality cell|100.0|6|column=brwiki|grouping=2023}}\n"
            '|- class="sortbottom"\n'
            "| '''Totals''' <small>(all items)</small>\n"
            "| 10 \n"
            "| {{Integraality cell|100.0|10|column=P1435|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=P131|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=P2929/P462|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=P1435/Q10387575/P580|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=Lbr|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=Dxy|grouping=}}\n"
            "| {{Integraality cell|100.0|10|column=brwiki|grouping=}}\n"
            "|}\n"
        )
        self.assertEqual(result, expected)
