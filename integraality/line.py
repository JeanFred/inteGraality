#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Line configuration classes
"""

import collections
import logging
import re

import pywikibot


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
    is_linkable = True

    def __init__(self, count, cells=None, title=None, higher_grouping=None):
        super().__init__(count, cells)
        self.title = title
        self.higher_grouping = higher_grouping

    def __eq__(self, other):
        return (
            self.count == other.count
            and self.title == other.title
            and self.higher_grouping == other.higher_grouping
            and self.cells == other.cells
        )

    def __repr__(self):
        cell = ",".join(["%s:%s" % (key, value) for (key, value) in self.cells.items()])
        return f"{self.title}:{self.count} - {cell}"

    def get_key(self):
        return self.title

    def format_header_cell(self, grouping_configuration, grouping_type):
        text = ""
        if self.higher_grouping is None:
            pass
        elif not grouping_configuration.higher_grouping:
            pass
        else:
            text += self.format_higher_grouping_text(grouping_type)

        text += f"| {self.heading()}\n"
        return text

    def format_cell(self, column_entry, cell_template):
        column_count = self.cells.get(column_entry.get_key(), 0)
        percentage = self.get_percentage(column_count)
        fields = [
            cell_template,
            str(percentage),
            str(column_count),
            f"column={column_entry.get_title()}",
            f"grouping={self.title}",
        ]
        return f'| {{{{{"|".join(fields)}}}}}\n'

    def row_opener(self):
        return "|-\n"

    def format_count_cell(self, grouping_link, repo):
        if grouping_link and self.is_linkable:
            return self.format_grouping_link(grouping_link, repo)
        else:
            return f"| {self.count} \n"

    def format_grouping_link(self, grouping_link, repo=None):
        return f"| [[{grouping_link}/{self.title}|{self.count}]] \n"

    def postive_query(self, selector_sparql, grouping_predicate=None, grouping=None):
        query = []
        query.extend(
            [
                "SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {",
                f"  ?entity {selector_sparql} .",
            ]
        )
        query.extend(
            self.postive_query_filter_out_fragment(grouping_predicate, grouping)
        )
        return "\n".join(query)

    def postive_query_filter_out_fragment(self, grouping_predicate=None, grouping=None):
        return []

    def negative_query(self, selector_sparql, grouping_predicate=None, grouping=None):
        query = []
        query.extend(
            [
                "SELECT DISTINCT ?entity ?entityLabel WHERE {",
                f"  ?entity {selector_sparql} .",
            ]
        )
        query.extend(
            self.negative_query_filter_out_fragment(grouping_predicate, grouping)
        )
        return "\n".join(query)

    def negative_query_filter_out_fragment(self, grouping_predicate=None, grouping=None):
        return self.postive_query_filter_out_fragment(grouping_predicate, grouping)


class NoGroupGrouping(Grouping):

    """Group for items that do not belong to any group."""

    is_linkable = False

    def heading(self):
        return "No grouping"

    def format_higher_grouping_text(self, grouping_type=None):
        return "|\n"

    def postive_query_filter_out_fragment(self, grouping_predicate, grouping=None):
        return ["  MINUS {", f"    ?entity {grouping_predicate} [] .", "  }"]

    def negative_query_filter_out_fragment(self, grouping_predicate, grouping=None):
        return [
            "  MINUS {",
            f"    {{?entity {grouping_predicate} [] .}} UNION",
        ]


class ItemGrouping(Grouping):
    def format_grouping_link(self, grouping_link, repo):
        try:
            group_item = pywikibot.ItemPage(repo, self.title)
            group_item.get(get_redirect=True)
            label = group_item.labels["en"]
        except (
            pywikibot.exceptions.InvalidTitleError,
            pywikibot.exceptions.NoPageError,
            KeyError,
        ):
            logging.info(f"Could not retrieve label for {self.title}")
            label = self.title
        return f"| [[{grouping_link}/{label}|{self.count}]] \n"

    def format_higher_grouping_text(self, grouping_type):
        higher_grouping_value = self.higher_grouping
        type_mapping = {
            "country": "{{Flag|%s}}" % higher_grouping_value,
        }
        if re.match(r"Q\d+", higher_grouping_value):
            higher_grouping_text = f"{{{{Q|{higher_grouping_value}}}}}"
        elif re.match(
            r"http://commons.wikimedia.org/wiki/Special:FilePath/(.*?)$",
            higher_grouping_value,
        ):
            match = re.match(
                r"http://commons.wikimedia.org/wiki/Special:FilePath/(.*?)$",
                higher_grouping_value,
            )
            image_name = match.groups()[0]
            higher_grouping_text = f"[[File:{image_name}|center|100px]]"
            higher_grouping_value = image_name
        elif grouping_type in type_mapping:
            higher_grouping_text = type_mapping.get(grouping_type)
        else:
            higher_grouping_text = higher_grouping_value
        return f'| data-sort-value="{higher_grouping_value}"| {higher_grouping_text}\n'

    def heading(self):
        return f"{{{{Q|{self.title}}}}}"

    def postive_query_filter_out_fragment(self, grouping_predicate, grouping):
        return [f"  ?entity {grouping_predicate} wd:{grouping} ."]

    def negative_query_filter_out_fragment(self, grouping_predicate, grouping):
        return self.postive_query_filter_out_fragment(grouping_predicate, grouping)


class YearGrouping(Grouping):
    def heading(self):
        return f"{self.title}"

    def postive_query_filter_out_fragment(self, grouping_predicate, grouping):
        return [
            f"  ?entity {grouping_predicate} ?date.",
            "  BIND(YEAR(?date) as ?year).",
            f"  FILTER(?year = {grouping}).",
        ]

    def negative_query_filter_out_fragment(self, grouping_predicate, grouping):
        return self.postive_query_filter_out_fragment(grouping_predicate, grouping)


class UnknownValueGrouping(Grouping):
    def get_key(self):
        return "UNKNOWN_VALUE"

    def heading(self):
        return "{{int:wikibase-snakview-variations-somevalue-label}}"

    def postive_query_filter_out_fragment(self, grouping_predicate, grouping=None):
        return [
            f"  ?entity {grouping_predicate} ?grouping.",
            "  FILTER wikibase:isSomeValue(?grouping).",
        ]

    def negative_query_filter_out_fragment(self, grouping_predicate, grouping):
        return self.postive_query_filter_out_fragment(grouping_predicate, grouping)


class TotalsGrouping(Grouping):
    is_linkable = False

    def heading(self):
        return "'''Totals''' <small>(all items)</small>"

    def format_higher_grouping_text(self, grouping_type=None):
        return "||\n"

    def row_opener(self):
        return '|- class="sortbottom"\n'
