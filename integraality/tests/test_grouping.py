# -*- coding: utf-8  -*-

import unittest

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
        expected = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity Q1 .\n"
            "  ?entity wdt:P1 ?grouping .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count >= 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assertEqual(result, expected)

    def test_get_grouping_information_query_with_threshold(self):
        grouping_configuration = grouping.ItemGroupingConfiguration(
            property="P1", grouping_threshold=12
        )
        result = grouping_configuration.get_grouping_information_query("Q1")
        expected = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity Q1 .\n"
            "  ?entity wdt:P1 ?grouping .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count >= 12)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assertEqual(result, expected)

    def test_get_grouping_information_query_with_higher_grouping(self):
        grouping_configuration = grouping.ItemGroupingConfiguration(
            property="P1", higher_grouping="wdt:P2"
        )
        result = grouping_configuration.get_grouping_information_query("Q1")
        expected = (
            "\n"
            "SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity Q1 .\n"
            "  ?entity wdt:P1 ?grouping .\n"
            "  OPTIONAL { ?grouping wdt:P2 ?_higher_grouping }.\n"
            "} GROUP BY ?grouping ?higher_grouping\n"
            "HAVING (?count >= 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
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
        expected = (
            "\n"
            "SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {\n"
            "  ?entity Q1 .\n"
            "  ?entity wdt:P1 ?date .\n"
            "  BIND(YEAR(?date) as ?grouping) .\n"
            "} GROUP BY ?grouping\n"
            "HAVING (?count >= 20)\n"
            "ORDER BY DESC(?count)\n"
            "LIMIT 1000\n"
        )
        self.assertEqual(result, expected)
