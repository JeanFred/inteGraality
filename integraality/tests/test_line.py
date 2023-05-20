# -*- coding: utf-8  -*-

import collections
import unittest

import line


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
        grouping = line.Grouping(count=1)

    def test_format_count_cell(self):
        grouping = line.Grouping(count=1, title="smth")
        result = grouping.format_count_cell(None, None)
        expected = "| 1 \n"
        self.assertEquals(result, expected)

    def test_format_count_cell_with_grouping_link(self):
        grouping = line.Grouping(count=1, title="smth")
        result = grouping.format_count_cell("Foo", None)
        expected = "| [[Foo/smth|1]] \n"
        self.assertEquals(result, expected)


class NoGroupGroupingTest(unittest.TestCase):
    def test_heading(self):
        grouping = line.NoGroupGrouping(count=1)
        result = grouping.heading()
        expected = "No grouping"
        self.assertEqual(result, expected)


class PropertyGroupingTest(unittest.TestCase):
    def test_heading(self):
        grouping = line.PropertyGrouping(count=1, title="Q1")
        result = grouping.heading()
        expected = "{{Q|Q1}}"
        self.assertEqual(result, expected)

    def test_format_header_cell(self):
        grouping = line.PropertyGrouping(count=1, title="Q1")
        result = grouping.format_header_cell(None)
        expected = "| {{Q|Q1}}\n"
        self.assertEqual(result, expected)

    def test_format_header_cell_with_higher_grouping(self):
        grouping = line.PropertyGrouping(count=1, title="Q1", higher_grouping="Q2")
        result = grouping.format_header_cell(None)
        expected = '| data-sort-value="Q2"| {{Q|Q2}}\n| {{Q|Q1}}\n'
        self.assertEqual(result, expected)


class YearGroupingTest(unittest.TestCase):
    def test_heading(self):
        grouping = line.YearGrouping(count=1, title="2001")
        result = grouping.heading()
        expected = "2001"
        self.assertEqual(result, expected)


class UnknownValueGroupingTest(unittest.TestCase):
    def test_heading(self):
        grouping = line.UnknownValueGrouping(count=1)
        result = grouping.heading()
        expected = "{{int:wikibase-snakview-variations-somevalue-label}}"
        self.assertEqual(result, expected)


class TotalsGroupingTest(unittest.TestCase):
    def test_heading(self):
        grouping = line.TotalsGrouping(count=1)
        result = grouping.heading()
        expected = "'''Totals''' <small>(all items)</small>"
        self.assertEqual(result, expected)


class FormatHigherGroupingTextTest(unittest.TestCase):
    def test_format_higher_grouping_text_default_qitem(self):
        higher_grouping = "Q1"
        grouping = line.PropertyGrouping(count=1, higher_grouping=higher_grouping)
        result = grouping.format_higher_grouping_text(None)
        expected = '| data-sort-value="Q1"| {{Q|Q1}}\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_string(self):
        higher_grouping = "foo"
        grouping = line.PropertyGrouping(count=1, higher_grouping=higher_grouping)
        result = grouping.format_higher_grouping_text(None)
        expected = '| data-sort-value="foo"| foo\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_country(self):
        higher_grouping = "AT"
        grouping = line.PropertyGrouping(count=1, higher_grouping=higher_grouping)
        result = grouping.format_higher_grouping_text("country")
        expected = '| data-sort-value="AT"| {{Flag|AT}}\n'
        self.assertEqual(result, expected)

    def test_format_higher_grouping_text_image(self):
        higher_grouping = (
            "http://commons.wikimedia.org/wiki/Special:FilePath/US%20CDC%20logo.svg"
        )
        grouping = line.PropertyGrouping(count=1, higher_grouping=higher_grouping)
        result = grouping.format_higher_grouping_text(None)
        expected = '| data-sort-value="US%20CDC%20logo.svg"| [[File:US%20CDC%20logo.svg|center|100px]]\n'
        self.assertEqual(result, expected)
