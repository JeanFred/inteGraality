# -*- coding: utf-8  -*-

import unittest

import line


class AbstractLineTest(unittest.TestCase):

    def test(self):
        abstract_line = line.AbstractLine(count=1)


class GroupingTest(unittest.TestCase):

    def test(self):
        grouping = line.Grouping(count=1)
