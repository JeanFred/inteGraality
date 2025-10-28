#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch

from sparql_utils import WdqsSparqlQueryEngine


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
