# -*- coding: utf-8  -*-

import collections
import unittest

from .. import line
from ..column import DescriptionColumn, LabelColumn, PropertyColumn, SitelinkColumn
from ..grouping import GroupingConfiguration, ItemGroupingType


class AbstractLineTest(unittest.TestCase):
    def test(self):
        abstract_line = line.AbstractLine(count=1)
        expected = collections.OrderedDict()
        self.assertEqual(abstract_line.cells, expected)

    def test_percentage_exact(self):
        abstract_line = line.AbstractLine(count=10)
        result = abstract_line.get_percentage(2)
        expected = 20.0
        self.assertEqual(result, expected)

    def test_percentage_rounded(self):
        abstract_line = line.AbstractLine(count=3)
        result = abstract_line.get_percentage(1)
        expected = 33.33
        self.assertEqual(result, expected)


class GroupingTest(unittest.TestCase):
    def test(self):
        line.Grouping(count=1)

    def test_format_count_cell(self):
        grouping = line.Grouping(count=1, title="smth")
        result = grouping.format_count_cell()
        expected = "| 1 \n"
        self.assertEqual(result, expected)

    def test_format_count_cell_with_grouping_link(self):
        grouping = line.Grouping(count=1, grouping_link="Foo/smth", title="smth")
        result = grouping.format_count_cell()
        expected = "| [[Foo/smth|1]] \n"
        self.assertEqual(result, expected)

    def test_format_count_cell_with_external_grouping_link(self):
        grouping = line.Grouping(
            count=10,
            grouping_link="https://scholia.toolforge.org/publisher/Q123",
            title="Q123",
        )
        result = grouping.format_count_cell()
        expected = "| [https://scholia.toolforge.org/publisher/Q123 10] \n"
        self.assertEqual(result, expected)

    def test_postive_query(self):
        grouping = line.Grouping(count=1)
        result = grouping.postive_query(selector_sparql="wdt:P31 wd:Q41960")
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
            ]
        )
        self.assertEqual(result, expected)

    def test_negative_query(self):
        grouping = line.Grouping(count=1)
        result = grouping.negative_query(selector_sparql="wdt:P31 wd:Q41960")
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
            ]
        )
        self.assertEqual(result, expected)


class NoGroupGroupingTest(unittest.TestCase):
    def test_heading(self):
        grouping = line.NoGroupGrouping(count=1)
        result = grouping.heading()
        expected = "No grouping"
        self.assertEqual(result, expected)

    def test_postive_query(self):
        grouping = line.NoGroupGrouping(count=1)
        result = grouping.postive_query(
            selector_sparql="wdt:P31 wd:Q41960",
            grouping_predicate="wdt:P551",
        )
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
                "  MINUS {",
                "    ?entity wdt:P551 [] .",
                "  }",
            ]
        )
        self.assertEqual(result, expected)

    def test_negative_query(self):
        grouping = line.NoGroupGrouping(count=1)
        result = grouping.negative_query(
            selector_sparql="wdt:P31 wd:Q41960",
            grouping_predicate="wdt:P551",
        )
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
                "  MINUS {",
                "    ?entity wdt:P551 [] .",
                "  }",
            ]
        )
        self.assertEqual(result, expected)


class ItemGroupingTest(unittest.TestCase):
    def test_heading(self):
        grouping = line.ItemGrouping(count=1, title="Q1")
        result = grouping.heading()
        expected = "{{Q|Q1}}"
        self.assertEqual(result, expected)

    def test_format_header_cell(self):
        grouping = line.ItemGrouping(count=1, title="Q1")
        result = grouping.format_header_cell(None, None)
        expected = "| {{Q|Q1}}\n"
        self.assertEqual(result, expected)

    def test_format_header_cell_with_higher_grouping(self):
        grouping = line.ItemGrouping(count=1, title="Q1", higher_grouping="Q2")
        grouping_configuration = GroupingConfiguration(
            predicate="wdt:P1",
            grouping_type=ItemGroupingType(),
            higher_grouping="XYZ",
        )
        result = grouping.format_header_cell(grouping_configuration, None)
        expected = '| data-sort-value="Q2"| {{Q|Q2}}\n| {{Q|Q1}}\n'
        self.assertEqual(result, expected)

    def test_postive_query(self):
        grouping = line.ItemGrouping(count=1)
        result = grouping.postive_query(
            selector_sparql="wdt:P31 wd:Q41960",
            grouping_predicate="wdt:P551",
            grouping="Q1",
        )
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
                "  ?entity wdt:P551 wd:Q1 .",
            ]
        )
        self.assertEqual(result, expected)

    def test_negative_query(self):
        grouping = line.ItemGrouping(count=1)
        result = grouping.negative_query(
            selector_sparql="wdt:P31 wd:Q41960",
            grouping_predicate="wdt:P551",
            grouping="Q1",
        )
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
                "  ?entity wdt:P551 wd:Q1 .",
            ]
        )
        self.assertEqual(result, expected)


class YearGroupingTest(unittest.TestCase):
    def test_heading(self):
        grouping = line.YearGrouping(count=1, title="2001")
        result = grouping.heading()
        expected = "2001"
        self.assertEqual(result, expected)

    def test_postive_query(self):
        grouping = line.YearGrouping(count=1)
        result = grouping.postive_query(
            selector_sparql="wdt:P31 wd:Q41960",
            grouping_predicate="wdt:P551",
            grouping="2001",
        )
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
                "  ?entity wdt:P551 ?date.",
                "  BIND(YEAR(?date) as ?year).",
                "  FILTER(?year = 2001).",
            ]
        )
        self.assertEqual(result, expected)

    def test_negative_query(self):
        grouping = line.YearGrouping(count=1)
        result = grouping.negative_query(
            selector_sparql="wdt:P31 wd:Q41960",
            grouping_predicate="wdt:P551",
            grouping="2001",
        )
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
                "  ?entity wdt:P551 ?date.",
                "  BIND(YEAR(?date) as ?year).",
                "  FILTER(?year = 2001).",
            ]
        )
        self.assertEqual(result, expected)


class UnknownValueGroupingTest(unittest.TestCase):
    def test_heading(self):
        grouping = line.UnknownValueGrouping(count=1)
        result = grouping.heading()
        expected = "{{int:wikibase-snakview-variations-somevalue-label}}"
        self.assertEqual(result, expected)

    def test_postive_query(self):
        grouping = line.UnknownValueGrouping(count=1)
        result = grouping.postive_query(
            selector_sparql="wdt:P31 wd:Q41960",
            grouping_predicate="wdt:P551",
        )
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
                "  ?entity wdt:P551 ?grouping.",
                "  FILTER(STRSTARTS(STR(?grouping), 'http://www.wikidata.org/.well-known/genid/')).",
            ]
        )
        self.assertEqual(result, expected)

    def test_negative_query(self):
        grouping = line.UnknownValueGrouping(count=1)
        result = grouping.negative_query(
            selector_sparql="wdt:P31 wd:Q41960",
            grouping_predicate="wdt:P551",
        )
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
                "  ?entity wdt:P551 ?grouping.",
                "  FILTER(STRSTARTS(STR(?grouping), 'http://www.wikidata.org/.well-known/genid/')).",
            ]
        )
        self.assertEqual(result, expected)


class TotalsGroupingTest(unittest.TestCase):
    def test_heading(self):
        grouping = line.TotalsGrouping(count=1)
        result = grouping.heading()
        expected = "'''Totals''' <small>(all items)</small>"
        self.assertEqual(result, expected)

    def test_postive_query(self):
        grouping = line.TotalsGrouping(count=1)
        result = grouping.postive_query(
            selector_sparql="wdt:P31 wd:Q41960",
            grouping_predicate="wdt:P551",
        )
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
            ]
        )
        self.assertEqual(result, expected)

    def test_negative_query(self):
        grouping = line.TotalsGrouping(count=1)
        result = grouping.negative_query(
            selector_sparql="wdt:P31 wd:Q41960",
            grouping_predicate="wdt:P551",
        )
        expected = "\n".join(
            [
                "SELECT DISTINCT ?entity ?entityLabel WHERE {",
                "  ?entity wdt:P31 wd:Q41960 .",
            ]
        )
        self.assertEqual(result, expected)


class FormatHigherGroupingTextTest(unittest.TestCase):
    def test_format_higher_grouping_text_default_qitem(self):
        higher_grouping = "Q1"
        grouping = line.ItemGrouping(count=1, higher_grouping=higher_grouping)
        result = grouping.format_higher_grouping_text(None)
        expected = '| data-sort-value="Q1"| {{Q|Q1}}\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_string(self):
        higher_grouping = "foo"
        grouping = line.ItemGrouping(count=1, higher_grouping=higher_grouping)
        result = grouping.format_higher_grouping_text(None)
        expected = '| data-sort-value="foo"| foo\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_country(self):
        higher_grouping = "AT"
        grouping = line.ItemGrouping(count=1, higher_grouping=higher_grouping)
        result = grouping.format_higher_grouping_text("country")
        expected = '| data-sort-value="AT"| {{Flag|AT}}\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_image(self):
        higher_grouping = (
            "http://commons.wikimedia.org/wiki/Special:FilePath/US%20CDC%20logo.svg"
        )
        grouping = line.ItemGrouping(count=1, higher_grouping=higher_grouping)
        result = grouping.format_higher_grouping_text(None)
        expected = '| data-sort-value="US%20CDC%20logo.svg"| [[File:US%20CDC%20logo.svg|center|100px]]\n'
        self.assertEqual(result, expected)


class ItemGroupingListeriaTest(unittest.TestCase):
    def test_format_listeria_wikitext(self):
        grouping = line.ItemGrouping(count=10, title="Q751719")
        columns = collections.OrderedDict(
            [
                ("P136", PropertyColumn("P136")),
                ("P178", PropertyColumn("P178")),
            ]
        )
        result = grouping.format_listeria_wikitext(
            selector_sparql="wdt:P31/wdt:P279* wd:Q7889",
            grouping_predicate="wdt:P400",
            columns=columns,
        )
        expected = (
            "{{Wikidata list|sparql=\n"
            "SELECT ?item WHERE {\n"
            "  ?item wdt:P31/wdt:P279* wd:Q7889.\n"
            "  ?item wdt:P400 wd:Q751719 .\n"
            "}\n"
            "|columns=P136,P178\n"
            "|summary=itemnumber\n"
            "}}\n"
            "{{Wikidata list end}}"
        )
        self.assertEqual(result, expected)

    def test_format_listeria_wikitext_with_label_and_description(self):
        grouping = line.ItemGrouping(count=5, title="Q42")
        columns = collections.OrderedDict(
            [
                ("Lde", LabelColumn("de")),
                ("P21", PropertyColumn("P21")),
                ("Dde", DescriptionColumn("de")),
            ]
        )
        result = grouping.format_listeria_wikitext(
            selector_sparql="wdt:P31 wd:Q5",
            grouping_predicate="wdt:P551",
            columns=columns,
        )
        expected = (
            "{{Wikidata list|sparql=\n"
            "SELECT ?item WHERE {\n"
            "  ?item wdt:P31 wd:Q5.\n"
            "  ?item wdt:P551 wd:Q42 .\n"
            "}\n"
            "|columns=label/de,description/de,P21\n"
            "|summary=itemnumber\n"
            "}}\n"
            "{{Wikidata list end}}"
        )
        self.assertEqual(result, expected)

    def test_format_listeria_wikitext_with_entity_in_selector(self):
        grouping = line.ItemGrouping(count=10, title="Q751719")
        columns = collections.OrderedDict([("P136", PropertyColumn("P136"))])
        result = grouping.format_listeria_wikitext(
            selector_sparql="wdt:P31/wdt:P279* wd:Q7889 . ?entity wdt:P400 wd:Q8093",
            grouping_predicate="wdt:P400",
            columns=columns,
        )
        self.assertNotIn("?entity", result)
        self.assertIn(
            "?item wdt:P31/wdt:P279* wd:Q7889 . ?item wdt:P400 wd:Q8093.", result
        )

    def test_format_listeria_wikitext_skips_sitelink_columns(self):
        grouping = line.ItemGrouping(count=5, title="Q42")
        columns = collections.OrderedDict(
            [
                ("P21", PropertyColumn("P21")),
                ("brwiki", SitelinkColumn("brwiki")),
            ]
        )
        result = grouping.format_listeria_wikitext(
            selector_sparql="wdt:P31 wd:Q5",
            grouping_predicate="wdt:P551",
            columns=columns,
        )
        self.assertIn("|columns=P21\n", result)
        self.assertNotIn("brwiki", result)


class YearGroupingListeriaTest(unittest.TestCase):
    def test_format_listeria_wikitext_decade(self):
        grouping = line.YearGrouping(count=10, title="1900", time_span=100)
        columns = collections.OrderedDict([("P17", PropertyColumn("P17"))])
        result = grouping.format_listeria_wikitext(
            selector_sparql="wdt:P31/wdt:P279* wd:Q811979",
            grouping_predicate="wdt:P571",
            columns=columns,
        )
        self.assertIn("FILTER(?year = 1900).", result)
        self.assertNotIn("1900/100", result)


class YearGroupingDisplayTest(unittest.TestCase):
    def test_heading_decade(self):
        self.assertEqual(
            line.YearGrouping(count=1, title="1950", time_span=10).heading(), "1950s"
        )

    def test_heading_century(self):
        self.assertEqual(
            line.YearGrouping(count=1, title="1900", time_span=100).heading(), "1900s"
        )

    def test_heading_millennium(self):
        self.assertEqual(
            line.YearGrouping(count=1, title="1000", time_span=1000).heading(), "1000s"
        )

    def test_heading_mega_annum(self):
        self.assertEqual(
            line.YearGrouping(count=1, title="-80000000", time_span=10000000).heading(),
            "-80 Ma",
        )

    def test_heading_kilo_annum(self):
        self.assertEqual(
            line.YearGrouping(count=1, title="-10000", time_span=10000).heading(),
            "-10 ka",
        )

    def test_query_filter_decade(self):
        result = line.YearGrouping(
            count=1, title="1950", time_span=10
        ).query_filter_out_fragment("wdt:P569", "1950")
        expected = [
            "  ?entity wdt:P569 ?date.",
            "  BIND(FLOOR(YEAR(?date) / 10) * 10 as ?year).",
            "  FILTER(?year = 1950).",
        ]
        self.assertEqual(result, expected)

    def test_query_filter_year(self):
        result = line.YearGrouping(count=1, title="1950").query_filter_out_fragment(
            "wdt:P569", "1950"
        )
        expected = [
            "  ?entity wdt:P569 ?date.",
            "  BIND(YEAR(?date) as ?year).",
            "  FILTER(?year = 1950).",
        ]
        self.assertEqual(result, expected)
