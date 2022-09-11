#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Line configuration classes
"""

import collections


class AbstractLine:

    def __init__(self, count, cells=None):
        self.count = count
        if not cells:
            cells = collections.OrderedDict()
        self.cells = cells


class Grouping(AbstractLine):

    def __init__(self, count, cells=None, title=None, higher_grouping=None):
        super().__init__(count, cells)
        self.title = title
        self.higher_grouping = higher_grouping

    def __eq__(self, other):
        return (
            self.count == other.count
            and self.title == other.title
            and self.higher_grouping == other.higher_grouping
        )

    def __repr__(self):
        return f'{self.title}:{self.count}'

    def get_key(self):
        return self.title


class PropertyGrouping(Grouping):

    def heading(self):
        return f"{{{{Q|{self.title}}}}}"


class YearGrouping(PropertyGrouping):

    def heading(self):
        return f"{self.title}"


class UnknownValueGrouping(Grouping):

    def get_key(self):
        return 'UNKNOWN_VALUE'

    def heading(self):
        return '{{int:wikibase-snakview-variations-somevalue-label}}'
