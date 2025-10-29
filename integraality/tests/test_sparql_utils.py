#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch
import pywikibot

from sparql_utils import WdqsSparqlQueryEngine, QueryException


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
