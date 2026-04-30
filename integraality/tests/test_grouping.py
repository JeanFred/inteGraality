# -*- coding: utf-8  -*-

import collections
import unittest
from unittest.mock import create_autospec

from .. import grouping
from ..grouping_link import LabelGroupingLink
from ..line import UnknownValueGrouping, YearGrouping
from ..sparql_utils import WdqsSparqlQueryEngine


class ItemGroupingConfigurationTest(unittest.TestCase):
    def test_get_grouping_selector(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="wdt:P1", grouping_type=grouping.ItemGroupingType()
        )
        result = grouping_configuration.get_grouping_selector()
        expected = ["  ?entity wdt:P1 ?grouping ."]
        self.assertListEqual(result, expected)

    def test_get_grouping_information_query(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="wdt:P1", grouping_type=grouping.ItemGroupingType()
        )
        result = grouping_configuration.get_grouping_information_query("Q1")
        expected = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity Q1 .
      ?entity wdt:P1 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)

    def test_get_grouping_information_query_with_threshold(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="wdt:P1",
            grouping_type=grouping.ItemGroupingType(),
            grouping_threshold=12,
        )
        result = grouping_configuration.get_grouping_information_query("Q1")
        expected = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity Q1 .
      ?entity wdt:P1 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 12)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)

    def test_get_grouping_information_query_with_higher_grouping(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="wdt:P1",
            grouping_type=grouping.ItemGroupingType(),
            higher_grouping="wdt:P2",
        )
        result = grouping_configuration.get_grouping_information_query("Q1")
        expected = """
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity Q1 .
      ?entity wdt:P1 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
  OPTIONAL { ?grouping wdt:P2 ?_higher_grouping }.
}
GROUP BY ?grouping ?count
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)

    def test_get_grouping_information_query_with_grouping_link(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="wdt:P1",
            grouping_type=grouping.ItemGroupingType(),
            higher_grouping="wdt:P2",
            grouping_link_type=LabelGroupingLink(template="Foo/{Len}"),
        )
        result = grouping_configuration.get_grouping_information_query("Q1")
        expected = """
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) ?grouping_link_value ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity Q1 .
      ?entity wdt:P1 ?grouping .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
  OPTIONAL { ?grouping wdt:P2 ?_higher_grouping }.
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
GROUP BY ?grouping ?grouping_link_value ?count
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)


class YearGroupingConfigurationTest(unittest.TestCase):
    def test_get_grouping_selector(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="wdt:P1", grouping_type=grouping.YearGroupingType()
        )
        result = grouping_configuration.get_grouping_selector()
        expected = ["  ?entity wdt:P1 ?date .", "  BIND(YEAR(?date) as ?grouping) ."]
        self.assertListEqual(result, expected)

    def test_get_grouping_information_query(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="wdt:P1", grouping_type=grouping.YearGroupingType()
        )
        result = grouping_configuration.get_grouping_information_query("Q1")
        expected = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity Q1 .
      ?entity wdt:P1 ?date .
      BIND(YEAR(?date) as ?grouping) .
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)

    def test_get_grouping_information_query_with_grouping_link(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="wdt:P1",
            grouping_type=grouping.YearGroupingType(),
            grouping_link_type=LabelGroupingLink(template="Foo/{Len}"),
        )
        result = grouping_configuration.get_grouping_information_query("Q1")
        expected = """
SELECT ?grouping ?grouping_link_value ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity Q1 .
      ?entity wdt:P1 ?date .
      BIND(YEAR(?date) as ?grouping) .
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
        self.assertEqual(result, expected)


class SitelinkGroupingConfigurationTest(unittest.TestCase):
    def test_get_grouping_selector(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="^schema:about", grouping_type=grouping.SitelinkGroupingType()
        )
        result = grouping_configuration.get_grouping_selector()
        expected = [
            "  ?entity ^schema:about ?sitelink.",
            "  ?sitelink schema:isPartOf ?grouping.",
        ]
        self.assertListEqual(result, expected)

    def test_get_grouping_information_query(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="^schema:about", grouping_type=grouping.SitelinkGroupingType()
        )
        result = grouping_configuration.get_grouping_information_query("Q1")
        expected = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity Q1 .
      ?entity ^schema:about ?sitelink.
      ?sitelink schema:isPartOf ?grouping.
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)

    def test_get_grouping_information_query_with_higher_grouping(self):
        grouping_configuration = grouping.GroupingConfiguration(
            predicate="^schema:about",
            grouping_type=grouping.SitelinkGroupingType(),
            higher_grouping="wikibase:wikiGroup",
        )
        result = grouping_configuration.get_grouping_information_query("Q1")
        expected = """
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity Q1 .
      ?entity ^schema:about ?sitelink.
      ?sitelink schema:isPartOf ?grouping.
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
  OPTIONAL { ?grouping wikibase:wikiGroup ?_higher_grouping }.
}
GROUP BY ?grouping ?count
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)


class TestGroupingConfigurationMaker(unittest.TestCase):
    def setUp(self):
        self.higher_grouping = "wdt:P17/wdt:P298"
        self.grouping_threshold = 5

    def test_simple_property(self):
        result = grouping.GroupingConfigurationMaker.make(
            "P136", self.higher_grouping, self.grouping_threshold
        )
        self.assertEqual(result.predicate, "wdt:P136")
        self.assertEqual(result.higher_grouping, self.higher_grouping)
        self.assertEqual(result.grouping_threshold, self.grouping_threshold)
        self.assertIsNone(result.grouping_type)

    def test_predicate_path(self):
        result = grouping.GroupingConfigurationMaker.make(
            "P131/wdt:P131", self.higher_grouping, self.grouping_threshold
        )
        self.assertEqual(result.predicate, "wdt:P131/wdt:P131")
        self.assertIsNone(result.grouping_type)

    def test_non_property_syntax(self):
        result = grouping.GroupingConfigurationMaker.make(
            "dct:language", self.higher_grouping, self.grouping_threshold
        )
        self.assertEqual(result.predicate, "dct:language")
        self.assertIsNone(result.grouping_type)

    def test_sitelink(self):
        result = grouping.GroupingConfigurationMaker.make(
            "schema:about", self.higher_grouping, self.grouping_threshold
        )
        self.assertEqual(result.predicate, "^schema:about")
        self.assertIsInstance(result.grouping_type, grouping.SitelinkGroupingType)

    def test_defers_explicit_groupings_parsing(self):
        result = grouping.GroupingConfigurationMaker.make(
            "P136", None, 20, explicit_groupings="Q1,Q2,Q3"
        )
        self.assertIsNone(result.explicit_groupings)
        self.assertEqual(result._raw_explicit_groupings, "Q1,Q2,Q3")


class TestDetectGroupingType(unittest.TestCase):
    def _detect(self, predicate, selector_sparql, engine):
        config = grouping.GroupingConfiguration(predicate=predicate)
        return config._detect_grouping_type(selector_sparql, engine)

    def test_datetime_returns_year(self):
        mock_engine = create_autospec(WdqsSparqlQueryEngine, instance=True)
        mock_engine.select.return_value = [
            {"datatype": "http://www.w3.org/2001/XMLSchema#dateTime"}
        ]
        result = self._detect("wdt:P569", "wdt:P31 wd:Q5", mock_engine)
        self.assertIsInstance(result, grouping.YearGroupingType)

    def test_no_datatype_returns_item(self):
        mock_engine = create_autospec(WdqsSparqlQueryEngine, instance=True)
        mock_engine.select.return_value = [{}]
        result = self._detect("wdt:P17", "wdt:P31 wd:Q5", mock_engine)
        self.assertIsInstance(result, grouping.ItemGroupingType)

    def test_empty_result_raises(self):
        from ..sparql_utils import QueryException

        mock_engine = create_autospec(WdqsSparqlQueryEngine, instance=True)
        mock_engine.select.return_value = []
        with self.assertRaises(QueryException):
            self._detect("wdt:P17", "wdt:P31 wd:Q5", mock_engine)

    def test_query_failure_propagates(self):
        from ..sparql_utils import QueryException

        mock_engine = create_autospec(WdqsSparqlQueryEngine, instance=True)
        mock_engine.select.side_effect = QueryException("timeout", query="")
        with self.assertRaises(QueryException):
            self._detect("wdt:P17", "wdt:P31 wd:Q5", mock_engine)

    def test_unsupported_datatype_raises(self):
        mock_engine = create_autospec(WdqsSparqlQueryEngine, instance=True)
        mock_engine.select.return_value = [
            {"datatype": "http://www.w3.org/2001/XMLSchema#string"}
        ]
        with self.assertRaises(grouping.UnsupportedGroupingConfigurationException):
            self._detect("wdt:P528", "wdt:P31 wd:Q5", mock_engine)


class TestResolveType(unittest.TestCase):
    def test_resolve_sets_grouping_type(self):
        mock_engine = create_autospec(WdqsSparqlQueryEngine, instance=True)
        mock_engine.select.return_value = [
            {"datatype": "http://www.w3.org/2001/XMLSchema#dateTime"}
        ]
        config = grouping.GroupingConfiguration(
            predicate="wdt:P569", raw_explicit_groupings="2020,2021"
        )
        config._resolve_type("wdt:P31 wd:Q5", mock_engine)
        self.assertIsInstance(config.grouping_type, grouping.YearGroupingType)
        self.assertEqual(config.explicit_groupings, [2020, 2021])

    def test_resolve_skips_if_type_already_set(self):
        mock_engine = create_autospec(WdqsSparqlQueryEngine, instance=True)
        config = grouping.GroupingConfiguration(
            predicate="wdt:P17", grouping_type=grouping.ItemGroupingType()
        )
        config._resolve_type("wdt:P31 wd:Q5", mock_engine)
        mock_engine.select.assert_not_called()


class TestParseGroupings(unittest.TestCase):
    def test_parse_item_groupings(self):
        result = grouping.ItemGroupingType.parse_groupings("Q1,Q2,Q3")
        expected = ["Q1", "Q2", "Q3"]
        self.assertEqual(result, expected)

    def test_parse_item_groupings_with_spaces(self):
        result = grouping.ItemGroupingType.parse_groupings("Q1, Q2 , Q3")
        expected = ["Q1", "Q2", "Q3"]
        self.assertEqual(result, expected)

    def test_parse_item_groupings_with_invalid(self):
        result = grouping.ItemGroupingType.parse_groupings("Q1,invalid,Q3")
        expected = ["Q1", "Q3"]
        self.assertEqual(result, expected)

    def test_parse_year_groupings(self):
        result = grouping.YearGroupingType.parse_groupings("2020,2021,2022")
        expected = [2020, 2021, 2022]
        self.assertEqual(result, expected)

    def test_parse_year_groupings_with_spaces(self):
        result = grouping.YearGroupingType.parse_groupings("2020, 2021 , 2022")
        expected = [2020, 2021, 2022]
        self.assertEqual(result, expected)

    def test_parse_year_groupings_with_invalid(self):
        result = grouping.YearGroupingType.parse_groupings("2020,invalid,2022")
        expected = [2020, 2022]
        self.assertEqual(result, expected)

    def test_parse_sitelink_groupings(self):
        result = grouping.SitelinkGroupingType.parse_groupings("enwiki,frwiki")
        expected = ["https://en.wikipedia.org/", "https://fr.wikipedia.org/"]
        self.assertEqual(result, expected)

    def test_parse_sitelink_groupings_with_spaces(self):
        result = grouping.SitelinkGroupingType.parse_groupings("enwiki, frwiki ")
        expected = ["https://en.wikipedia.org/", "https://fr.wikipedia.org/"]
        self.assertEqual(result, expected)

    def test_parse_sitelink_groupings_with_invalid(self):
        result = grouping.SitelinkGroupingType.parse_groupings(
            "enwiki,invalidwiki,frwiki"
        )
        expected = ["https://en.wikipedia.org/", "https://fr.wikipedia.org/"]
        self.assertEqual(result, expected)


class TestExplicitGroupings(unittest.TestCase):
    def test_item_grouping_get_values_clause(self):
        config = grouping.GroupingConfiguration(
            predicate="wdt:P1",
            grouping_type=grouping.ItemGroupingType(),
            explicit_groupings=["Q1", "Q2", "Q3"],
        )
        result = config.get_values_clause()
        expected = ["  VALUES ?grouping { wd:Q1 wd:Q2 wd:Q3 }"]
        self.assertEqual(result, expected)

    def test_item_grouping_query_with_explicit_groupings(self):
        config = grouping.GroupingConfiguration(
            predicate="wdt:P1",
            grouping_type=grouping.ItemGroupingType(),
            explicit_groupings=["Q1", "Q2"],
        )
        result = config.get_grouping_information_query("wdt:P31 wd:Q5")
        expected = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q5 .
      ?entity wdt:P1 ?grouping .
      VALUES ?grouping { wd:Q1 wd:Q2 }
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)

    def test_year_grouping_get_values_clause(self):
        config = grouping.GroupingConfiguration(
            predicate="wdt:P1",
            grouping_type=grouping.YearGroupingType(),
            explicit_groupings=[2020, 2021, 2022],
        )
        result = config.get_values_clause()
        expected = ["  VALUES ?grouping { 2020 2021 2022 }"]
        self.assertEqual(result, expected)

    def test_year_grouping_query_with_explicit_groupings(self):
        config = grouping.GroupingConfiguration(
            predicate="wdt:P577",
            grouping_type=grouping.YearGroupingType(),
            explicit_groupings=[2020, 2021],
        )
        result = config.get_grouping_information_query("wdt:P31 wd:Q5")
        expected = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q5 .
      ?entity wdt:P577 ?date .
      BIND(YEAR(?date) as ?grouping) .
      VALUES ?grouping { 2020 2021 }
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)

    def test_sitelink_grouping_get_values_clause(self):
        config = grouping.GroupingConfiguration(
            predicate="^schema:about",
            grouping_type=grouping.SitelinkGroupingType(),
            explicit_groupings=[
                "https://en.wikipedia.org/",
                "https://fr.wikipedia.org/",
            ],
        )
        result = config.get_values_clause()
        expected = [
            "  VALUES ?grouping { <https://en.wikipedia.org/> <https://fr.wikipedia.org/> }"
        ]
        self.assertEqual(result, expected)

    def test_sitelink_grouping_query_with_explicit_groupings(self):
        config = grouping.GroupingConfiguration(
            predicate="^schema:about",
            grouping_type=grouping.SitelinkGroupingType(),
            explicit_groupings=[
                "https://en.wikipedia.org/",
                "https://fr.wikipedia.org/",
            ],
        )
        result = config.get_grouping_information_query("wdt:P31 wd:Q5")
        expected = """
SELECT ?grouping ?count WHERE {
  {
    SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
      ?entity wdt:P31 wd:Q5 .
      ?entity ^schema:about ?sitelink.
      ?sitelink schema:isPartOf ?grouping.
      VALUES ?grouping { <https://en.wikipedia.org/> <https://fr.wikipedia.org/> }
    }
    GROUP BY ?grouping
    HAVING (?count >= 20)
  }
}
ORDER BY DESC(?count)
LIMIT 1000
"""
        self.assertEqual(result, expected)

    def test_predicate_grouping_get_values_clause(self):
        config = grouping.GroupingConfiguration(
            predicate="wdt:P1",
            explicit_groupings=["Q1", "Q2"],
            grouping_type=grouping.ItemGroupingType(),
        )
        result = config.get_values_clause()
        expected = ["  VALUES ?grouping { wd:Q1 wd:Q2 }"]
        self.assertEqual(result, expected)


class YearRebinningTest(unittest.TestCase):
    def setUp(self):
        self.config = grouping.GroupingConfiguration(
            predicate="wdt:P569", grouping_type=grouping.YearGroupingType()
        )

    def test_full_path_with_outlier(self):
        mock_engine = create_autospec(WdqsSparqlQueryEngine, instance=True)
        years = list(range(1903, 2027)) + [3]  # 125 years with outlier
        mock_engine.select.return_value = [
            {"grouping": str(year), "count": "5"} for year in years
        ]

        result = self.config.get_grouping_information("wdt:P31 wd:Q482994", mock_engine)
        result = self.config.post_process(result)

        self.assertEqual(len(result), 14)  # 1 (0s) + 13 (1900s-2020s)
        self.assertIsInstance(result["1900/10"], YearGrouping)
        self.assertEqual(result["1900/10"].time_span, 10)
        self.assertIn("0/10", result)

    def test_no_rebinning_for_small_count(self):
        groupings = collections.OrderedDict(
            (str(year), YearGrouping(title=str(year), count=5))
            for year in range(1950, 2000)
        )
        result = self.config.post_process(groupings)
        self.assertEqual(len(result), 50)
        self.assertIsInstance(result["1950"], YearGrouping)

    def test_rebin_to_decade_for_large_count(self):
        groupings = collections.OrderedDict(
            (str(year), YearGrouping(title=str(year), count=5))
            for year in range(1900, 2025)
        )
        result = self.config.post_process(groupings)
        self.assertLess(len(result), 125)
        self.assertEqual(result["1900/10"].time_span, 10)

    def test_ignores_unknown_value(self):
        groupings = collections.OrderedDict(
            (str(year), YearGrouping(title=str(year), count=5))
            for year in range(1950, 2000)
        )
        groupings["UNKNOWN_VALUE"] = UnknownValueGrouping(count=3)
        result = self.config.post_process(groupings)
        self.assertEqual(len(result), 51)  # 50 years + UNKNOWN_VALUE
        self.assertIsInstance(result["1950"], YearGrouping)

    def test_rebin_sums_counts_and_cells(self):
        groupings = collections.OrderedDict(
            [
                (
                    "1995",
                    YearGrouping(
                        title="1995",
                        count=10,
                        cells=collections.OrderedDict([("P1", 5)]),
                    ),
                ),
                (
                    "1996",
                    YearGrouping(
                        title="1996",
                        count=8,
                        cells=collections.OrderedDict([("P1", 4)]),
                    ),
                ),
                (
                    "2001",
                    YearGrouping(
                        title="2001",
                        count=12,
                        cells=collections.OrderedDict([("P1", 6)]),
                    ),
                ),
            ]
        )
        # Force >100 entries so rebinning triggers
        for year in range(1800, 1900):
            groupings[str(year)] = YearGrouping(
                title=str(year), count=1, cells=collections.OrderedDict([("P1", 1)])
            )

        result = self.config.post_process(groupings)

        self.assertIn("1990/10", result)
        self.assertIn("2000/10", result)
        self.assertEqual(result["1990/10"].count, 18)
        self.assertEqual(result["1990/10"].cells["P1"], 9)
        self.assertEqual(result["1990/10"].time_span, 10)

    def test_rebin_preserves_unknown_value(self):
        groupings = collections.OrderedDict(
            (str(year), YearGrouping(title=str(year), count=5))
            for year in range(1800, 2025)
        )
        groupings["UNKNOWN_VALUE"] = UnknownValueGrouping(count=5)

        result = self.config.post_process(groupings)

        self.assertIn("UNKNOWN_VALUE", result)
        self.assertEqual(result["UNKNOWN_VALUE"].count, 5)
