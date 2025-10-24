# -*- coding: utf-8  -*-

import unittest
from unittest.mock import patch

import grouping


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
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity Q1 .
  ?entity wdt:P1 ?grouping .
} GROUP BY ?grouping
HAVING (?count >= 20)
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
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity Q1 .
  ?entity wdt:P1 ?grouping .
} GROUP BY ?grouping
HAVING (?count >= 12)
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
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity Q1 .
  ?entity wdt:P1 ?grouping .
  OPTIONAL { ?grouping wdt:P2 ?_higher_grouping }.
} GROUP BY ?grouping
HAVING (?count >= 20)
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
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) ?grouping_link_value (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity Q1 .
  ?entity wdt:P1 ?grouping .
  OPTIONAL { ?grouping wdt:P2 ?_higher_grouping }.
  OPTIONAL {{
    ?grouping rdfs:label ?labelMUL.
    FILTER(lang(?labelMUL)='mul')
  }}.
  OPTIONAL {{
    ?grouping rdfs:label ?labelEN.
    FILTER(lang(?labelEN)='en')
  }}.
  BIND(COALESCE(?labelEN, ?labelMUL) AS ?grouping_link_value).
} GROUP BY ?grouping ?grouping_link_value
HAVING (?count >= 20)
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
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity Q1 .
  ?entity wdt:P1 ?date .
  BIND(YEAR(?date) as ?grouping) .
} GROUP BY ?grouping
HAVING (?count >= 20)
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
SELECT ?grouping ?grouping_link_value (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity Q1 .
  ?entity wdt:P1 ?date .
  BIND(YEAR(?date) as ?grouping) .
  OPTIONAL {{
    ?grouping rdfs:label ?labelMUL.
    FILTER(lang(?labelMUL)='mul')
  }}.
  OPTIONAL {{
    ?grouping rdfs:label ?labelEN.
    FILTER(lang(?labelEN)='en')
  }}.
  BIND(COALESCE(?labelEN, ?labelMUL) AS ?grouping_link_value).
} GROUP BY ?grouping ?grouping_link_value
HAVING (?count >= 20)
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
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity Q1 .
  ?entity ^schema:about ?sitelink.
  ?sitelink schema:isPartOf ?grouping.
} GROUP BY ?grouping
HAVING (?count >= 20)
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
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) (COUNT(DISTINCT ?entity) as ?count) WHERE {
  ?entity Q1 .
  ?entity ^schema:about ?sitelink.
  ?sitelink schema:isPartOf ?grouping.
  OPTIONAL { ?grouping wikibase:wikiGroup ?_higher_grouping }.
} GROUP BY ?grouping
HAVING (?count >= 20)
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
