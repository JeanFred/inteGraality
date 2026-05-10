# -*- coding: utf-8  -*-
"""Unit tests for config_assembler.py."""

import unittest

from ..column import DescriptionColumn, LabelColumn, PropertyColumn
from ..config_assembler import ConfigAssembler, ConfigAssemblyException
from ..grouping import GroupingConfiguration
from ..grouping_link import LabelGroupingLink
from ..sparql_utils import QLeverSparqlQueryEngine, WdqsSparqlQueryEngine


class TestParseConfig(unittest.TestCase):
    def setUp(self):
        self.assembler = ConfigAssembler(site_url="https://www.wikidata.org/wiki/")

    def test_normal_config(self):
        input_config = {
            "grouping_link": "Wikidata:WikiProject Video games/Reports/Platform",
            "grouping_property": "P400",
            "stats_for_no_group": "1",
            "properties": "P136:genre,P404",
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
        }
        result = self.assembler.parse_config(input_config)
        expected = {
            "grouping_configuration": GroupingConfiguration(
                predicate="wdt:P400",
                grouping_link_type=LabelGroupingLink(
                    template="Wikidata:WikiProject Video games/Reports/Platform/{Len}",
                ),
            ),
            "stats_for_no_group": True,
            "columns": [
                PropertyColumn(property="P136", title="genre"),
                PropertyColumn(property="P404"),
            ],
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
            "grouping_link_mode": "link",
        }
        self.assertIsInstance(result.pop("sparql_query_engine"), WdqsSparqlQueryEngine)
        self.assertEqual(result, expected)

    def test_minimal_config(self):
        input_config = {
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
            "grouping_property": "P400",
            "properties": "P136:genre,P404",
        }
        result = self.assembler.parse_config(input_config)
        expected = {
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
            "grouping_configuration": GroupingConfiguration(predicate="wdt:P400"),
            "columns": [
                PropertyColumn(property="P136", title="genre"),
                PropertyColumn(property="P404"),
            ],
            "stats_for_no_group": False,
            "grouping_link_mode": "link",
        }
        self.assertIsInstance(result.pop("sparql_query_engine"), WdqsSparqlQueryEngine)
        self.assertEqual(result, expected)

    def test_full_config(self):
        input_config = {
            "grouping_property": "P400",
            "stats_for_no_group": "1",
            "properties": "P136:genre,P404",
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
            "grouping_threshold": "1",
            "property_threshold": "2",
        }
        result = self.assembler.parse_config(input_config)
        expected = {
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
            "grouping_configuration": GroupingConfiguration(
                predicate="wdt:P400", grouping_threshold=1
            ),
            "columns": [
                PropertyColumn(property="P136", title="genre"),
                PropertyColumn(property="P404"),
            ],
            "stats_for_no_group": True,
            "property_threshold": "2",
            "grouping_link_mode": "link",
        }
        self.assertIsInstance(result.pop("sparql_query_engine"), WdqsSparqlQueryEngine)
        self.assertEqual(result, expected)

    def test_empty_config(self):
        input_config = {}
        with self.assertRaises(ConfigAssemblyException):
            self.assembler.parse_config(input_config)

    def test_insufficient_config(self):
        input_config = {
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
        }
        with self.assertRaises(ConfigAssemblyException):
            self.assembler.parse_config(input_config)

    def test_config_with_grouping_link_mode_create(self):
        input_config = {
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
            "grouping_property": "P400",
            "properties": "P136,P404",
            "grouping_link": "Foo",
            "grouping_link_mode": "create",
        }
        result = self.assembler.parse_config(input_config)
        self.assertEqual(result["grouping_link_mode"], "create")

    def test_config_with_invalid_grouping_link_mode(self):
        input_config = {
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
            "grouping_property": "P400",
            "properties": "P136,P404",
            "grouping_link_mode": "crate",
        }
        with self.assertRaises(ConfigAssemblyException):
            self.assembler.parse_config(input_config)

    def test_config_with_qlever_endpoint(self):
        input_config = {
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
            "grouping_property": "P400",
            "properties": "P136:genre,P404",
            "sparql_endpoint": "https://qlever.dev/wikidata/",
        }
        result = self.assembler.parse_config(input_config)
        self.assertIsInstance(result["sparql_query_engine"], QLeverSparqlQueryEngine)

    def test_config_with_commons_site_url(self):
        assembler = ConfigAssembler(site_url="https://commons.wikimedia.org/wiki/")
        input_config = {
            "selector_sparql": '(p:P170/pq:P4174) "Coyau"',
            "grouping_property": "P571",
            "properties": "P4082,P180",
        }
        result = assembler.parse_config(input_config)
        self.assertIsInstance(result["sparql_query_engine"], QLeverSparqlQueryEngine)
        self.assertEqual(
            result["sparql_query_engine"].endpoint,
            "https://qlever.dev/api/wikimedia-commons",
        )

    def test_config_with_wdqs_endpoint(self):
        input_config = {
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
            "grouping_property": "P400",
            "properties": "P136:genre,P404",
            "sparql_endpoint": "query.wikidata.org",
        }
        result = self.assembler.parse_config(input_config)
        self.assertIsInstance(result["sparql_query_engine"], WdqsSparqlQueryEngine)


class TestParseParams(unittest.TestCase):
    def setUp(self):
        self.assembler = ConfigAssembler(site_url="https://www.wikidata.org/wiki/")

    def test_parse_config_from_params_minimal(self):
        params = [
            "grouping_property=P195",
            "properties=P170:creator,P276",
            "selector_sparql=wdt:P31 wd:Q3305213",
        ]
        expected = {
            "grouping_property": "P195",
            "properties": "P170:creator,P276",
            "selector_sparql": "wdt:P31 wd:Q3305213",
        }
        result = self.assembler.parse_config_from_params(params)
        self.assertEqual(result, expected)

    def test_parse_config_from_params_with_empty_param(self):
        params = [
            "",
            "grouping_property=P195",
            "properties=P170:creator,P276",
            "selector_sparql=wdt:P31 wd:Q3305213",
        ]
        expected = {
            "grouping_property": "P195",
            "properties": "P170:creator,P276",
            "selector_sparql": "wdt:P31 wd:Q3305213",
        }
        result = self.assembler.parse_config_from_params(params)
        self.assertEqual(result, expected)

    def test_parse_config_from_params_with_escaped_pipe(self):
        params = [
            "grouping_property=P195",
            "properties=P170:creator,P276",
            'selector_sparql=REGEX(?id, "^(a{{!}}b)")',
        ]
        expected = {
            "grouping_property": "P195",
            "properties": "P170:creator,P276",
            "selector_sparql": 'REGEX(?id, "^(a|b)")',
        }
        result = self.assembler.parse_config_from_params(params)
        self.assertEqual(result, expected)


class TestParseConfigProperties(unittest.TestCase):
    def setUp(self):
        self.assembler = ConfigAssembler(site_url="https://www.wikidata.org/wiki/")

    def test(self):
        properties = "P136:genre,P404"
        result = self.assembler.parse_config_properties(properties)
        expected = [
            PropertyColumn(property="P136", title="genre"),
            PropertyColumn(property="P404"),
        ]
        self.assertEqual(result, expected)

    def test_with_trail_comma(self):
        properties = "P136:genre,P404,"
        result = self.assembler.parse_config_properties(properties)
        expected = [
            PropertyColumn(property="P136", title="genre"),
            PropertyColumn(property="P404"),
        ]
        self.assertEqual(result, expected)

    def test_more_properties(self):
        properties = "P136,P178,P123,P495,P577,P404,P437"
        result = self.assembler.parse_config_properties(properties)
        expected = [
            PropertyColumn(property="P136"),
            PropertyColumn(property="P178"),
            PropertyColumn(property="P123"),
            PropertyColumn(property="P495"),
            PropertyColumn(property="P577"),
            PropertyColumn(property="P404"),
            PropertyColumn(property="P437"),
        ]
        self.assertEqual(result, expected)

    def test_with_qualifier(self):
        properties = "P136:genre,P404,P669/P670"
        result = self.assembler.parse_config_properties(properties)
        expected = [
            PropertyColumn(property="P136", title="genre"),
            PropertyColumn(property="P404"),
            PropertyColumn(property="P669", qualifier="P670"),
        ]
        self.assertEqual(result, expected)

    def test_with_qualifier_and_value(self):
        properties = "P136:genre,P404,P553/Q17459/P670"
        result = self.assembler.parse_config_properties(properties)
        expected = [
            PropertyColumn(property="P136", title="genre"),
            PropertyColumn(property="P404"),
            PropertyColumn(property="P553", value="Q17459", qualifier="P670"),
        ]
        self.assertEqual(result, expected)

    def test_with_label(self):
        properties = "P136:genre,Lbr,P553"
        result = self.assembler.parse_config_properties(properties)
        expected = [
            PropertyColumn(property="P136", title="genre"),
            LabelColumn(language="br"),
            PropertyColumn(property="P553"),
        ]
        self.assertEqual(result, expected)

    def test_with_description(self):
        properties = "P136:genre,Lxy,P553"
        result = self.assembler.parse_config_properties(properties)
        expected = [
            PropertyColumn(property="P136", title="genre"),
            DescriptionColumn(language="xy"),
            PropertyColumn(property="P553"),
        ]
        self.assertEqual(result, expected)

    def test_with_space(self):
        properties = "P131, P17"
        result = self.assembler.parse_config_properties(properties)
        expected = [PropertyColumn(property="P131"), PropertyColumn(property="P17")]
        self.assertEqual(result, expected)

    def test_with_incorrect_syntax(self):
        properties = "P131,Something"
        with self.assertRaises(ConfigAssemblyException):
            self.assembler.parse_config_properties(properties)
