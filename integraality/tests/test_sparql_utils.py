#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch

import pywikibot
import requests

from sparql_utils import (
    add_prefixes_to_query,
    QLeverSparqlQueryEngine,
    QueryException,
    SparqlEngineBuilder,
    UnsupportedSparqlEngineException,
    WdqsSparqlQueryEngine,
)


class WdqsSparqlQueryEngineTest(unittest.TestCase):
    @patch("sparql_utils.pywikibot.data.sparql.SparqlQuery")
    def test_select(self, mock_sparql_query_class):
        mock_sq = Mock()
        mock_sq.select.return_value = [{"count": "42"}]
        mock_sparql_query_class.return_value = mock_sq

        engine = WdqsSparqlQueryEngine()
        result = engine.select("SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }")

        expected = [{"count": "42"}]
        self.assertEqual(result, expected)
        mock_sq.select.assert_called_once_with(
            "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
        )

    @patch("sparql_utils.pywikibot.data.sparql.SparqlQuery")
    def test_select_timeout_error(self, mock_sparql_query_class):
        mock_sq = Mock()
        mock_sq.select.side_effect = pywikibot.exceptions.TimeoutError("Timeout")
        mock_sparql_query_class.return_value = mock_sq

        engine = WdqsSparqlQueryEngine()
        with self.assertRaises(QueryException) as cm:
            engine.select("SELECT * WHERE { ?s ?p ?o }")

        self.assertIn(
            "The Wikidata Query Service timed out when running a SPARQL query",
            str(cm.exception),
        )
        self.assertEqual(cm.exception.query, "SELECT * WHERE { ?s ?p ?o }")


class QLeverSparqlQueryEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = QLeverSparqlQueryEngine()

    @patch("requests.get")
    def test_select_success(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": {
                "bindings": [
                    {"entity": {"value": "http://www.wikidata.org/entity/Q1"}},
                    {"entity": {"value": "http://www.wikidata.org/entity/Q2"}},
                ]
            }
        }
        mock_get.return_value = mock_response

        result = self.engine.select("SELECT ?entity WHERE { ?entity wdt:P31 wd:Q5 }")

        expected = [
            {"entity": "http://www.wikidata.org/entity/Q1"},
            {"entity": "http://www.wikidata.org/entity/Q2"},
        ]
        self.assertEqual(result, expected)

    @patch("requests.get")
    def test_select_timeout_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        with self.assertRaises(QueryException) as cm:
            self.engine.select("SELECT ?entity WHERE { ?entity wdt:P31 wd:Q5 }")

        self.assertIn("QLever timed out", str(cm.exception))
        self.assertIsNotNone(cm.exception.query)

    @patch("requests.get")
    def test_select_503(self, mock_get):
        mock_get.side_effect = requests.exceptions.HTTPError()

        with self.assertRaises(QueryException) as cm:
            self.engine.select("SELECT ?entity WHERE { ?entity wdt:P31 wd:Q5 }")

        self.assertIn("QLever is not available", str(cm.exception))
        self.assertIsNotNone(cm.exception.query)

    def test_transform_response_valid(self):
        data = {
            "results": {
                "bindings": [
                    {"entity": {"value": "http://www.wikidata.org/entity/Q1"}},
                    {"count": {"value": "42"}},
                ]
            }
        }
        result = self.engine._transform_response(data)
        expected = [{"entity": "http://www.wikidata.org/entity/Q1"}, {"count": "42"}]
        self.assertEqual(result, expected)

    def test_transform_response_empty(self):
        empty_data = {}
        result = self.engine._transform_response(empty_data)
        self.assertEqual(result, [])

    def test_transform_response_grouping_query(self):
        # Test with actual QLever API response format
        grouping_data = {
            "results": {
                "bindings": [
                    {
                        "grouping": {
                            "type": "uri",
                            "value": "http://www.wikidata.org/entity/Q2047427",
                        },
                        "higher_grouping": {"type": "literal", "value": "CHN"},
                        "grouping_link_value": {
                            "type": "literal",
                            "value": "The Palace Museum",
                            "xml:lang": "en",
                        },
                        "count": {
                            "datatype": "http://www.w3.org/2001/XMLSchema#int",
                            "type": "literal",
                            "value": "46762",
                        },
                    },
                    {
                        "grouping": {
                            "type": "uri",
                            "value": "http://www.wikidata.org/entity/Q812285",
                        },
                        "count": {
                            "datatype": "http://www.w3.org/2001/XMLSchema#int",
                            "type": "literal",
                            "value": "18009",
                        },
                    },
                ]
            }
        }
        result = self.engine._transform_response(grouping_data)
        expected = [
            {
                "grouping": "http://www.wikidata.org/entity/Q2047427",
                "higher_grouping": "CHN",
                "grouping_link_value": "The Palace Museum",
                "count": "46762",
            },
            {"grouping": "http://www.wikidata.org/entity/Q812285", "count": "18009"},
        ]
        self.assertEqual(result, expected)


class AddPrefixesToQueryTest(unittest.TestCase):
    def test_add_prefixes_to_query(self):
        query = "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }"
        result = add_prefixes_to_query(query)

        self.assertIn("PREFIX wd: <http://www.wikidata.org/entity/>", result)
        self.assertIn("PREFIX wdt: <http://www.wikidata.org/prop/direct/>", result)
        self.assertIn(query, result)
        self.assertTrue(result.endswith(query))


class SparqlEngineBuilderTest(unittest.TestCase):
    def test_create_qlever_engine_url(self):
        engine = SparqlEngineBuilder.make("https://qlever.dev/api/wikidata")
        self.assertIsInstance(engine, QLeverSparqlQueryEngine)
        self.assertEqual(engine.endpoint, "https://qlever.dev/api/wikidata")

    def test_create_qlever_engine_name(self):
        engine = SparqlEngineBuilder.make("qlever")
        self.assertIsInstance(engine, QLeverSparqlQueryEngine)
        self.assertEqual(engine.endpoint, "https://qlever.dev/api/wikidata")

    def test_create_wdqs_engine_wdqs(self):
        engine = SparqlEngineBuilder.make("query.wikidata.org")
        self.assertIsInstance(engine, WdqsSparqlQueryEngine)

    def test_create_wdqs_engine_default(self):
        engine = SparqlEngineBuilder.make()
        self.assertIsInstance(engine, WdqsSparqlQueryEngine)

    def test_create_wdqs_engine_unsupported(self):
        with self.assertRaises(UnsupportedSparqlEngineException):
            SparqlEngineBuilder.make("foo")
