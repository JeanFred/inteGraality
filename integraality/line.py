#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Line configuration classes
"""


class AbstractLine:

    def __init__(self, count):
        self.count = count


class Grouping(AbstractLine):

    def __init__(self, count, title=None, higher_grouping=None):
        super().__init__(count)
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
    pass


class YearGrouping(PropertyGrouping):
    pass


class UnknownValueGrouping(Grouping):

    def get_key(self):
        return 'UNKNOWN_VALUE'
