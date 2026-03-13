# -*- coding: utf-8  -*-

import collections
import unittest
from unittest.mock import create_autospec, patch

import grouping
from line import UnknownValueGrouping, YearGrouping
from sparql_utils import WdqsSparqlQueryEngine


class AbstractGroupingConfiguration(unittest.TestCase):
    def test_constructor_empty(self):
        grouping.AbstractGroupingConfiguration()

    def test_get_grouping_selector(self):
        grouping_configuration = grouping.AbstractGroupingConfiguration()
        with self.assertRaises(NotImplementedError):
            grouping_configuration.get_grouping_selector()

    def test_get_grouping_information_query(self):
        grouping_configuration = grouping.AbstractGroupingConfiguration()
        with self.assertRaises(NotImplementedError):
            grouping_configuration.get_grouping_information_query("Q1")


class ItemGroupingConfigurationTest(unittest.TestCase):
    def test_constructor_empty(self):
        grouping.ItemGroupingConfiguration(property=None)

    def test_get_grouping_selector(self):
        grouping_configuration = grouping.ItemGroupingConfiguration(property="P1")
        result = grouping_configuration.get_grouping_selector()
        expected = ["  ?entity wdt:P1 ?grouping ."]
        self.assertListEqual(result, expected)

    def test_get_grouping_information_query(self):
        grouping_configuration = grouping.ItemGroupingConfiguration(property="P1")
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
        grouping_configuration = grouping.ItemGroupingConfiguration(
            property="P1", grouping_threshold=12
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
        grouping_configuration = grouping.ItemGroupingConfiguration(
            property="P1", higher_grouping="wdt:P2"
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
        grouping_configuration = grouping.ItemGroupingConfiguration(
            property="P1", higher_grouping="wdt:P2", base_grouping_link="Foo"
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
    def test_constructor_empty(self):
        grouping.YearGroupingConfiguration(property=None)

    def test_get_grouping_selector(self):
        grouping_configuration = grouping.YearGroupingConfiguration(property="P1")
        result = grouping_configuration.get_grouping_selector()
        expected = ["  ?entity wdt:P1 ?date .", "  BIND(YEAR(?date) as ?grouping) ."]
        self.assertListEqual(result, expected)

    def test_get_grouping_information_query(self):
        grouping_configuration = grouping.YearGroupingConfiguration(property="P1")
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
        grouping_configuration = grouping.YearGroupingConfiguration(
            property="P1", base_grouping_link="Foo"
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
    def test_constructor_empty(self):
        grouping.SitelinkGroupingConfiguration()

    def test_get_grouping_selector(self):
        grouping_configuration = grouping.SitelinkGroupingConfiguration()
        result = grouping_configuration.get_grouping_selector()
        expected = [
            "  ?entity ^schema:about ?sitelink.",
            "  ?sitelink schema:isPartOf ?grouping.",
        ]
        self.assertListEqual(result, expected)

    def test_get_grouping_information_query(self):
        grouping_configuration = grouping.SitelinkGroupingConfiguration()
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
        grouping_configuration = grouping.SitelinkGroupingConfiguration(
            higher_grouping="wikibase:wikiGroup"
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
        patcher = patch("pywikibot.PropertyPage", autospec=True)
        self.mock_property_page = patcher.start()
        self.addCleanup(patcher.stop)
        self.higher_grouping = "wdt:P17/wdt:P298"
        self.grouping_threshold = 5

    def test_item_datatype(self):
        self.mock_property_page.return_value.get_data_for_new_entity.return_value = {
            "datatype": "wikibase-item"
        }
        result = grouping.GroupingConfigurationMaker.make(
            None, "P136", self.higher_grouping, self.grouping_threshold
        )
        expected = grouping.ItemGroupingConfiguration(
            property="P136",
            higher_grouping=self.higher_grouping,
            grouping_threshold=self.grouping_threshold,
        )
        self.assertEqual(result, expected)

    def test_time_datatype(self):
        self.mock_property_page.return_value.get_data_for_new_entity.return_value = {
            "datatype": "time"
        }
        result = grouping.GroupingConfigurationMaker.make(
            None, "P569", self.higher_grouping, self.grouping_threshold
        )
        expected = grouping.YearGroupingConfiguration(
            property="P569", grouping_threshold=self.grouping_threshold
        )
        self.assertEqual(result, expected)

    def test_unsupported_datatype(self):
        self.mock_property_page.return_value.get_data_for_new_entity.return_value = {
            "datatype": "string"
        }
        with self.assertRaises(grouping.UnsupportedGroupingConfigurationException):
            grouping.GroupingConfigurationMaker.make(
                None, "P528", self.higher_grouping, self.grouping_threshold
            )

    def test_non_property_syntax(self):
        result = grouping.GroupingConfigurationMaker.make(
            None, "dct:language", self.higher_grouping, self.grouping_threshold
        )
        expected = grouping.PredicateGroupingConfiguration(
            predicate="dct:language",
            higher_grouping=self.higher_grouping,
            grouping_threshold=self.grouping_threshold,
        )
        self.assertEqual(result, expected)

    def test_property_syntax_with_injection(self):
        result = grouping.GroupingConfigurationMaker.make(
            None, "P131/wdt:P131", self.higher_grouping, self.grouping_threshold
        )
        expected = grouping.PredicateGroupingConfiguration(
            predicate="wdt:P131/wdt:P131",
            higher_grouping=self.higher_grouping,
            grouping_threshold=self.grouping_threshold,
        )
        self.assertEqual(result, expected)

    def test_sitelink(self):
        result = grouping.GroupingConfigurationMaker.make(
            None, "schema:about", self.higher_grouping, self.grouping_threshold
        )
        expected = grouping.SitelinkGroupingConfiguration(
            higher_grouping=self.higher_grouping,
            grouping_threshold=self.grouping_threshold,
        )
        self.assertEqual(result, expected)


class TestParseGroupings(unittest.TestCase):
    def test_parse_item_groupings(self):
        result = grouping.ItemGroupingConfiguration.parse_groupings("Q1,Q2,Q3")
        expected = ["Q1", "Q2", "Q3"]
        self.assertEqual(result, expected)

    def test_parse_item_groupings_with_spaces(self):
        result = grouping.ItemGroupingConfiguration.parse_groupings("Q1, Q2 , Q3")
        expected = ["Q1", "Q2", "Q3"]
        self.assertEqual(result, expected)

    def test_parse_item_groupings_with_invalid(self):
        result = grouping.ItemGroupingConfiguration.parse_groupings("Q1,invalid,Q3")
        expected = ["Q1", "Q3"]
        self.assertEqual(result, expected)

    def test_parse_year_groupings(self):
        result = grouping.YearGroupingConfiguration.parse_groupings("2020,2021,2022")
        expected = [2020, 2021, 2022]
        self.assertEqual(result, expected)

    def test_parse_year_groupings_with_spaces(self):
        result = grouping.YearGroupingConfiguration.parse_groupings("2020, 2021 , 2022")
        expected = [2020, 2021, 2022]
        self.assertEqual(result, expected)

    def test_parse_year_groupings_with_invalid(self):
        result = grouping.YearGroupingConfiguration.parse_groupings("2020,invalid,2022")
        expected = [2020, 2022]
        self.assertEqual(result, expected)

    def test_parse_sitelink_groupings(self):
        result = grouping.SitelinkGroupingConfiguration.parse_groupings("enwiki,frwiki")
        expected = ["https://en.wikipedia.org/", "https://fr.wikipedia.org/"]
        self.assertEqual(result, expected)

    def test_parse_sitelink_groupings_with_spaces(self):
        result = grouping.SitelinkGroupingConfiguration.parse_groupings(
            "enwiki, frwiki "
        )
        expected = ["https://en.wikipedia.org/", "https://fr.wikipedia.org/"]
        self.assertEqual(result, expected)

    def test_parse_sitelink_groupings_with_invalid(self):
        result = grouping.SitelinkGroupingConfiguration.parse_groupings(
            "enwiki,invalidwiki,frwiki"
        )
        expected = ["https://en.wikipedia.org/", "https://fr.wikipedia.org/"]
        self.assertEqual(result, expected)


class TestExplicitGroupings(unittest.TestCase):
    def test_item_grouping_get_values_clause(self):
        config = grouping.ItemGroupingConfiguration(
            property="P1", explicit_groupings=["Q1", "Q2", "Q3"]
        )
        result = config.get_values_clause()
        expected = ["  VALUES ?grouping { wd:Q1 wd:Q2 wd:Q3 }"]
        self.assertEqual(result, expected)

    def test_item_grouping_query_with_explicit_groupings(self):
        config = grouping.ItemGroupingConfiguration(
            property="P1", explicit_groupings=["Q1", "Q2"]
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
        config = grouping.YearGroupingConfiguration(
            property="P1", explicit_groupings=[2020, 2021, 2022]
        )
        result = config.get_values_clause()
        expected = ["  VALUES ?grouping { 2020 2021 2022 }"]
        self.assertEqual(result, expected)

    def test_year_grouping_query_with_explicit_groupings(self):
        config = grouping.YearGroupingConfiguration(
            property="P577", explicit_groupings=[2020, 2021]
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
        config = grouping.SitelinkGroupingConfiguration(
            explicit_groupings=[
                "https://en.wikipedia.org/",
                "https://fr.wikipedia.org/",
            ]
        )
        result = config.get_values_clause()
        expected = [
            "  VALUES ?grouping { <https://en.wikipedia.org/> <https://fr.wikipedia.org/> }"
        ]
        self.assertEqual(result, expected)

    def test_sitelink_grouping_query_with_explicit_groupings(self):
        config = grouping.SitelinkGroupingConfiguration(
            explicit_groupings=[
                "https://en.wikipedia.org/",
                "https://fr.wikipedia.org/",
            ]
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
        config = grouping.PredicateGroupingConfiguration(
            predicate="wdt:P1", explicit_groupings=["Q1", "Q2"]
        )
        result = config.get_values_clause()
        expected = ["  VALUES ?grouping { wd:Q1 wd:Q2 }"]
        self.assertEqual(result, expected)


class YearRebinningTest(unittest.TestCase):
    def setUp(self):
        self.config = grouping.YearGroupingConfiguration(property="P569")

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
        result = self.config._rebin_if_needed(groupings)
        self.assertEqual(len(result), 50)
        self.assertIsInstance(result["1950"], YearGrouping)

    def test_rebin_to_decade_for_large_count(self):
        groupings = collections.OrderedDict(
            (str(year), YearGrouping(title=str(year), count=5))
            for year in range(1900, 2025)
        )
        result = self.config._rebin_if_needed(groupings)
        self.assertLess(len(result), 125)
        self.assertEqual(result["1900/10"].time_span, 10)

    def test_ignores_unknown_value(self):
        groupings = collections.OrderedDict(
            (str(year), YearGrouping(title=str(year), count=5))
            for year in range(1950, 2000)
        )
        groupings["UNKNOWN_VALUE"] = UnknownValueGrouping(count=3)
        result = self.config._rebin_if_needed(groupings)
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

        result = self.config._rebin_if_needed(groupings)

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

        result = self.config._rebin_if_needed(groupings)

        self.assertIn("UNKNOWN_VALUE", result)
        self.assertEqual(result["UNKNOWN_VALUE"].count, 5)
