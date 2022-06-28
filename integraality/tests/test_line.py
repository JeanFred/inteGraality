# -*- coding: utf-8  -*-

import unittest

import line


class AbstractLineTest(unittest.TestCase):

    def test(self):
        abstract_line = line.AbstractLine(count=1)


class GroupingTest(unittest.TestCase):

    def test(self):
        grouping = line.Grouping(count=1)


class PropertyGroupingTest(unittest.TestCase):

    def test_heading(self):
        grouping = line.PropertyGrouping(count=1, title='Q1')
        result = grouping.heading()
        expected = "{{Q|Q1}}"
        self.assertEqual(result, expected)


class YearGroupingTest(unittest.TestCase):

    def test_heading(self):
        grouping = line.YearGrouping(count=1, title='2001')
        result = grouping.heading()
        expected = "2001"
        self.assertEqual(result, expected)


class UnknownValueGroupingTest(unittest.TestCase):

    def test_heading(self):
        grouping = line.UnknownValueGrouping(count=1)
        result = grouping.heading()
        expected = "{{int:wikibase-snakview-variations-somevalue-label}}"
        self.assertEqual(result, expected)
