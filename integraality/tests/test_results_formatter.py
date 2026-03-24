# -*- coding: utf-8  -*-
"""Unit tests for results_formatter.py."""

import unittest
from collections import OrderedDict

from ..column import LabelColumn, PropertyColumn, SitelinkColumn
from ..grouping import GroupingConfiguration, ItemGroupingType
from ..line import (
    ItemGrouping,
    NoGroupGrouping,
    SitelinkGrouping,
    TotalsGrouping,
    UnknownValueGrouping,
    YearGrouping,
)
from ..results_formatter import ResultsFormatter


class ResultsFormatterTest(unittest.TestCase):
    def setUp(self):
        self.columns = {
            "P21": PropertyColumn(property="P21"),
            "P19": PropertyColumn(property="P19"),
            "Lbr": LabelColumn(language="br"),
        }
        self.grouping_configuration = GroupingConfiguration(
            predicate="wdt:P551",
            grouping_type=ItemGroupingType(),
            grouping_threshold=20,
        )
        self.formatter = ResultsFormatter(
            columns=self.columns,
            grouping_configuration=self.grouping_configuration,
            property_threshold=10,
        )


class TestFormatHeader(ResultsFormatterTest):
    def test_format_header(self):
        result = self.formatter._format_header()
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="3"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
        )
        self.assertEqual(result, expected)

    def test_format_header_with_higher_grouping(self):
        self.formatter.grouping_configuration.higher_grouping = "wdt:P17/wdt:P298"
        result = self.formatter._format_header()
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="3" |Top groupings (Minimum 20 items)\n'
            '! colspan="3"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! \n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
        )
        self.assertEqual(result, expected)


class TestFormatGrouping(ResultsFormatterTest):
    def test_format_grouping(self):
        grouping = ItemGrouping(title="Q3115846", count=10)
        grouping.cells = OrderedDict([("P21", 10), ("P19", 8), ("Lbr", 1)])
        result = self.formatter._format_grouping(grouping)
        expected = (
            "|-\n"
            "| {{Q|Q3115846}}\n"
            "| 10 \n"
            "| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n"
            "| {{Integraality cell|80.0|8|column=P19|grouping=Q3115846}}\n"
            "| {{Integraality cell|10.0|1|column=Lbr|grouping=Q3115846}}\n"
        )
        self.assertEqual(result, expected)

    def test_format_grouping_with_higher_grouping(self):
        self.formatter.grouping_configuration.higher_grouping = "wdt:P17/wdt:P298"
        grouping = ItemGrouping(title="Q3115846", count=10, higher_grouping="Q1")
        grouping.cells = OrderedDict([("P21", 10), ("P19", 8), ("Lbr", 1)])
        result = self.formatter._format_grouping(grouping)
        expected = (
            "|-\n"
            '| data-sort-value="Q1"| {{Q|Q1}}\n'
            "| {{Q|Q3115846}}\n"
            "| 10 \n"
            "| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n"
            "| {{Integraality cell|80.0|8|column=P19|grouping=Q3115846}}\n"
            "| {{Integraality cell|10.0|1|column=Lbr|grouping=Q3115846}}\n"
        )
        self.assertEqual(result, expected)

    def test_format_grouping_custom_cell_template(self):
        formatter = ResultsFormatter(
            columns=self.columns,
            grouping_configuration=self.grouping_configuration,
            property_threshold=10,
            cell_template="Custom cell",
        )
        grouping = ItemGrouping(title="Q3115846", count=10)
        grouping.cells = OrderedDict([("P21", 10), ("P19", 8), ("Lbr", 1)])
        result = formatter._format_grouping(grouping)
        expected = (
            "|-\n"
            "| {{Q|Q3115846}}\n"
            "| 10 \n"
            "| {{Custom cell|100.0|10|column=P21|grouping=Q3115846}}\n"
            "| {{Custom cell|80.0|8|column=P19|grouping=Q3115846}}\n"
            "| {{Custom cell|10.0|1|column=Lbr|grouping=Q3115846}}\n"
        )
        self.assertEqual(result, expected)

    def test_format_year_grouping(self):
        grouping = YearGrouping(title="2001", count=10)
        grouping.cells = OrderedDict([("P21", 4), ("P19", 0), ("Lbr", 0)])
        result = self.formatter._format_grouping(grouping)
        expected = (
            "|-\n"
            "| 2001\n"
            "| 10 \n"
            "| {{Integraality cell|40.0|4|column=P21|grouping=2001}}\n"
            "| {{Integraality cell|0|0|column=P19|grouping=2001}}\n"
            "| {{Integraality cell|0|0|column=Lbr|grouping=2001}}\n"
        )
        self.assertEqual(result, expected)

    def test_format_year_grouping_with_grouping_link(self):
        grouping = YearGrouping(title="2001", grouping_link="Foo/2001", count=10)
        grouping.cells = OrderedDict([("P21", 4), ("P19", 0), ("Lbr", 0)])
        result = self.formatter._format_grouping(grouping)
        expected = (
            "|-\n"
            "| 2001\n"
            "| [[Foo/2001|10]] \n"
            "| {{Integraality cell|40.0|4|column=P21|grouping=2001}}\n"
            "| {{Integraality cell|0|0|column=P19|grouping=2001}}\n"
            "| {{Integraality cell|0|0|column=Lbr|grouping=2001}}\n"
        )
        self.assertEqual(result, expected)

    def test_format_unknown_value_grouping(self):
        grouping = UnknownValueGrouping(count=10)
        grouping.cells = OrderedDict([("P21", 4), ("P19", 0), ("Lbr", 0)])
        result = self.formatter._format_grouping(grouping)
        expected = (
            "|-\n"
            "| {{int:wikibase-snakview-variations-somevalue-label}}\n"
            "| 10 \n"
            "| {{Integraality cell|40.0|4|column=P21|grouping=UNKNOWN_VALUE}}\n"
            "| {{Integraality cell|0|0|column=P19|grouping=UNKNOWN_VALUE}}\n"
            "| {{Integraality cell|0|0|column=Lbr|grouping=UNKNOWN_VALUE}}\n"
        )
        self.assertEqual(result, expected)

    def test_format_unknown_value_grouping_with_grouping_link(self):
        grouping = UnknownValueGrouping(grouping_link="Foo/UNKNOWN_VALUE", count=10)
        grouping.cells = OrderedDict([("P21", 4), ("P19", 0), ("Lbr", 0)])
        result = self.formatter._format_grouping(grouping)
        expected = (
            "|-\n"
            "| {{int:wikibase-snakview-variations-somevalue-label}}\n"
            "| [[Foo/UNKNOWN_VALUE|10]] \n"
            "| {{Integraality cell|40.0|4|column=P21|grouping=UNKNOWN_VALUE}}\n"
            "| {{Integraality cell|0|0|column=P19|grouping=UNKNOWN_VALUE}}\n"
            "| {{Integraality cell|0|0|column=Lbr|grouping=UNKNOWN_VALUE}}\n"
        )
        self.assertEqual(result, expected)

    def test_format_grouping_with_grouping_link(self):
        grouping = ItemGrouping(title="Q3115846", grouping_link="Foo/Bar", count=10)
        grouping.cells = OrderedDict([("P21", 10), ("P19", 8), ("Lbr", 1)])
        result = self.formatter._format_grouping(grouping)
        expected = (
            "|-\n"
            "| {{Q|Q3115846}}\n"
            "| [[Foo/Bar|10]] \n"
            "| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n"
            "| {{Integraality cell|80.0|8|column=P19|grouping=Q3115846}}\n"
            "| {{Integraality cell|10.0|1|column=Lbr|grouping=Q3115846}}\n"
        )
        self.assertEqual(result, expected)

    def test_format_sitelink_grouping(self):
        grouping = SitelinkGrouping(title="https://en.wikipedia.org/", count=10)
        grouping.cells = OrderedDict([("P21", 5), ("P19", 3), ("Lbr", 2)])
        result = self.formatter._format_grouping(grouping)
        expected = (
            "|-\n"
            "| https://en.wikipedia.org/\n"
            "| 10 \n"
            "| {{Integraality cell|50.0|5|column=P21|grouping=https://en.wikipedia.org/}}\n"
            "| {{Integraality cell|30.0|3|column=P19|grouping=https://en.wikipedia.org/}}\n"
            "| {{Integraality cell|20.0|2|column=Lbr|grouping=https://en.wikipedia.org/}}\n"
        )
        self.assertEqual(result, expected)


class TestFormatReport(ResultsFormatterTest):
    def test_format_report_empty(self):
        result = self.formatter.format_report([])
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="3"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            "|}\n"
        )
        self.assertEqual(result, expected)

    def test_format_report_with_groupings(self):
        grouping1 = ItemGrouping(title="Q3115846", count=10)
        grouping1.cells = OrderedDict([("P21", 10), ("P19", 8), ("Lbr", 1)])
        grouping2 = ItemGrouping(title="Q5087901", count=6)
        grouping2.cells = OrderedDict([("P21", 6), ("P19", 0), ("Lbr", 0)])

        result = self.formatter.format_report([grouping1, grouping2])
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="3"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            "|-\n"
            "| {{Q|Q3115846}}\n"
            "| 10 \n"
            "| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n"
            "| {{Integraality cell|80.0|8|column=P19|grouping=Q3115846}}\n"
            "| {{Integraality cell|10.0|1|column=Lbr|grouping=Q3115846}}\n"
            "|-\n"
            "| {{Q|Q5087901}}\n"
            "| 6 \n"
            "| {{Integraality cell|100.0|6|column=P21|grouping=Q5087901}}\n"
            "| {{Integraality cell|0|0|column=P19|grouping=Q5087901}}\n"
            "| {{Integraality cell|0|0|column=Lbr|grouping=Q5087901}}\n"
            "|}\n"
        )
        self.assertEqual(result, expected)

    def test_format_report_with_no_group_and_totals(self):
        grouping1 = ItemGrouping(title="Q3115846", count=10)
        grouping1.cells = OrderedDict([("P21", 10), ("P19", 8), ("Lbr", 1)])

        no_group = NoGroupGrouping(count=5)
        no_group.cells = OrderedDict([("P21", 2), ("P19", 3), ("Lbr", 0)])

        totals = TotalsGrouping(count=15, title="")
        totals.cells = OrderedDict([("P21", 12), ("P19", 11), ("Lbr", 1)])

        result = self.formatter.format_report([grouping1, no_group, totals])
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="3"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            "|-\n"
            "| {{Q|Q3115846}}\n"
            "| 10 \n"
            "| {{Integraality cell|100.0|10|column=P21|grouping=Q3115846}}\n"
            "| {{Integraality cell|80.0|8|column=P19|grouping=Q3115846}}\n"
            "| {{Integraality cell|10.0|1|column=Lbr|grouping=Q3115846}}\n"
            "|-\n"
            "| No grouping\n"
            "| 5 \n"
            "| {{Integraality cell|40.0|2|column=P21|grouping=None}}\n"
            "| {{Integraality cell|60.0|3|column=P19|grouping=None}}\n"
            "| {{Integraality cell|0|0|column=Lbr|grouping=None}}\n"
            '|- class="sortbottom"\n'
            "| '''Totals''' <small>(all items)</small>\n"
            "| 15 \n"
            "| {{Integraality cell|80.0|12|column=P21|grouping=}}\n"
            "| {{Integraality cell|73.33|11|column=P19|grouping=}}\n"
            "| {{Integraality cell|6.67|1|column=Lbr|grouping=}}\n"
            "|}\n"
        )
        self.assertEqual(result, expected)

    def test_format_report_with_year_groupings(self):
        year1 = YearGrouping(title="2001", count=10)
        year1.cells = OrderedDict([("P21", 4), ("P19", 2), ("Lbr", 1)])
        year2 = YearGrouping(title="2018", count=6)
        year2.cells = OrderedDict([("P21", 6), ("P19", 0), ("Lbr", 0)])

        totals = TotalsGrouping(count=16, title="")
        totals.cells = OrderedDict([("P21", 10), ("P19", 2), ("Lbr", 1)])

        result = self.formatter.format_report([year1, year2, totals])
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="3"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            "|-\n"
            "| 2001\n"
            "| 10 \n"
            "| {{Integraality cell|40.0|4|column=P21|grouping=2001}}\n"
            "| {{Integraality cell|20.0|2|column=P19|grouping=2001}}\n"
            "| {{Integraality cell|10.0|1|column=Lbr|grouping=2001}}\n"
            "|-\n"
            "| 2018\n"
            "| 6 \n"
            "| {{Integraality cell|100.0|6|column=P21|grouping=2018}}\n"
            "| {{Integraality cell|0|0|column=P19|grouping=2018}}\n"
            "| {{Integraality cell|0|0|column=Lbr|grouping=2018}}\n"
            '|- class="sortbottom"\n'
            "| '''Totals''' <small>(all items)</small>\n"
            "| 16 \n"
            "| {{Integraality cell|62.5|10|column=P21|grouping=}}\n"
            "| {{Integraality cell|12.5|2|column=P19|grouping=}}\n"
            "| {{Integraality cell|6.25|1|column=Lbr|grouping=}}\n"
            "|}\n"
        )
        self.assertEqual(result, expected)

    def test_format_report_with_sitelink_groupings(self):
        sitelink1 = SitelinkGrouping(title="https://en.wikipedia.org/", count=10)
        sitelink1.cells = OrderedDict([("P21", 5), ("P19", 3), ("Lbr", 2)])
        sitelink2 = SitelinkGrouping(title="https://fr.wikipedia.org/", count=8)
        sitelink2.cells = OrderedDict([("P21", 4), ("P19", 2), ("Lbr", 1)])

        result = self.formatter.format_report([sitelink1, sitelink2])
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="3"|Top Properties (used at least 10 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Property|P19}}\n'
            '! data-sort-type="number"|{{#language:br}}\n'
            "|-\n"
            "| https://en.wikipedia.org/\n"
            "| 10 \n"
            "| {{Integraality cell|50.0|5|column=P21|grouping=https://en.wikipedia.org/}}\n"
            "| {{Integraality cell|30.0|3|column=P19|grouping=https://en.wikipedia.org/}}\n"
            "| {{Integraality cell|20.0|2|column=Lbr|grouping=https://en.wikipedia.org/}}\n"
            "|-\n"
            "| https://fr.wikipedia.org/\n"
            "| 8 \n"
            "| {{Integraality cell|50.0|4|column=P21|grouping=https://fr.wikipedia.org/}}\n"
            "| {{Integraality cell|25.0|2|column=P19|grouping=https://fr.wikipedia.org/}}\n"
            "| {{Integraality cell|12.5|1|column=Lbr|grouping=https://fr.wikipedia.org/}}\n"
            "|}\n"
        )
        self.assertEqual(result, expected)

    def test_format_report_with_sitelink_column(self):
        """Test formatting with SitelinkColumn in the columns."""
        columns = {
            "P21": PropertyColumn(property="P21"),
            "enwiki": SitelinkColumn(project="enwiki"),
        }
        formatter = ResultsFormatter(
            columns=columns,
            grouping_configuration=self.grouping_configuration,
            property_threshold=5,
        )

        grouping = ItemGrouping(title="Q123", count=10)
        grouping.cells = OrderedDict([("P21", 8), ("enwiki", 6)])

        result = formatter.format_report([grouping])
        expected = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" |Top groupings (Minimum 20 items)\n'
            '! colspan="2"|Top Properties (used at least 5 times per grouping)\n'
            "|-\n"
            "! Name\n"
            "! Count\n"
            '! data-sort-type="number"|{{Property|P21}}\n'
            '! data-sort-type="number"|{{Q|Q328}}\n'
            "|-\n"
            "| {{Q|Q123}}\n"
            "| 10 \n"
            "| {{Integraality cell|80.0|8|column=P21|grouping=Q123}}\n"
            "| {{Integraality cell|60.0|6|column=enwiki|grouping=Q123}}\n"
            "|}\n"
        )
        self.assertEqual(result, expected)
