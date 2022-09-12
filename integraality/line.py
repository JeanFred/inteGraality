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

    def get_percentage(self, value):
        if not value:
            return 0
        return round(1.0 * value / max(self.count, 1) * 100, 2)


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

    def format_cell(self, column_entry, cell_template):
        column_count = self.cells.get(column_entry.get_key(), 0)
        percentage = self.get_percentage(column_count)
        fields = [
            cell_template,
            str(percentage),
            str(column_count),
            f"column={column_entry.get_title()}",
            f"grouping={self.title}"
        ]
        return f'| {{{{{"|".join(fields)}}}}}\n'


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
