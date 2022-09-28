#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Calculate and generate statistics

"""
import collections
import logging
from enum import Enum

import pywikibot
import pywikibot.data.sparql

from column import ColumnMaker, GroupingType
from line import PropertyGrouping, UnknownValueGrouping
from statsd.defaults.env import statsd


class QueryException(Exception):

    def __init__(self, message, query):
        super().__init__(message)
        self.query = query


class PropertyStatistics:
    """
    Generate statitics

    """
    UNKNOWN_VALUE_PREFIX = "http://www.wikidata.org/.well-known/genid/"

    GROUP_MAPPING = Enum('GROUP_MAPPING', {
        'NO_GROUPING': 'None',
        'TOTALS': '',
        'UNKNOWN_VALUE': '{{int:wikibase-snakview-variations-somevalue-label}}'
    })

    def __init__(self, selector_sparql, columns, grouping_property, grouping_type=None, higher_grouping=None, higher_grouping_type=None, stats_for_no_group=False, grouping_link=None, grouping_threshold=20, property_threshold=0):  # noqa
        """
        Set what to work on and other variables here.
        """
        site = pywikibot.Site('en', 'wikipedia')
        self.repo = site.data_repository()
        self.columns = {column.get_key(): column for column in columns}
        self.grouping_property = grouping_property
        if grouping_type:
            self.grouping_type = GroupingType(grouping_type)
        else:
            self.grouping_type = None
        self.higher_grouping = higher_grouping
        self.higher_grouping_type = higher_grouping_type
        self.selector_sparql = selector_sparql
        self.stats_for_no_group = stats_for_no_group
        self.grouping_threshold = grouping_threshold
        self.property_threshold = property_threshold

        self.grouping_link = grouping_link
        self.cell_template = 'Integraality cell'

    @statsd.timer('property_statistics.sparql.groupings')
    def get_grouping_information(self):
        """
        Get all groupings and their counts.

        :return: List of Grouping objects
        """
        if self.higher_grouping:
            query = f"""
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) (COUNT(DISTINCT ?entity) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?grouping .
  OPTIONAL {{ ?grouping {self.higher_grouping} ?_higher_grouping }}.
}} GROUP BY ?grouping ?higher_grouping
HAVING (?count >= {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 1000
"""
        elif self.grouping_type == GroupingType.YEAR:
            query = f"""
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?date .
  BIND(YEAR(?date) as ?grouping) .
}} GROUP BY ?grouping
HAVING (?count >= {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 1000
"""
        else:
            query = f"""
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?grouping .
}} GROUP BY ?grouping
HAVING (?count >= {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 1000
"""
        groupings = collections.OrderedDict()

        try:
            sq = pywikibot.data.sparql.SparqlQuery()
            queryresult = sq.select(query)

            if not queryresult:
                raise QueryException(
                    "No result when querying groupings."
                    "Please investigate the 'all groupings' debug query in the dashboard header.",
                    query=query
                )

        except pywikibot.exceptions.TimeoutError:

            raise QueryException(
                "The Wikidata Query Service timed out when fetching groupings."
                "You might be trying to do something too expensive."
                "Please investigate the 'all groupings' debug query in the dashboard header.",
                query=query
            )

        unknown_value_count = 0

        for resultitem in queryresult:

            if not resultitem.get('grouping') or resultitem.get('grouping').startswith(self.UNKNOWN_VALUE_PREFIX):
                unknown_value_count += int(resultitem.get('count'))

            else:
                qid = resultitem.get('grouping').replace(u'http://www.wikidata.org/entity/', u'')
                if self.higher_grouping:
                    value = resultitem.get('higher_grouping')
                    if value:
                        value = value.replace(u'http://www.wikidata.org/entity/', u'')
                    higher_grouping = value
                else:
                    higher_grouping = None
                property_grouping = PropertyGrouping(title=qid, count=int(resultitem.get('count')), higher_grouping=higher_grouping)
                groupings[property_grouping.get_key()] = property_grouping

        if unknown_value_count:
            unknown_value_grouping = UnknownValueGrouping(unknown_value_count)
            groupings[unknown_value_grouping.get_key()] = unknown_value_grouping

        return groupings

    def get_query_for_items_for_property_positive(self, column, grouping):
        column_key = column.get_key()
        query = f"""
SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {{
  ?entity {self.selector_sparql} ."""

        if grouping == self.GROUP_MAPPING.TOTALS:
            pass

        elif grouping == self.GROUP_MAPPING.NO_GROUPING:
            query += f"""
  MINUS {{
    ?entity wdt:{self.grouping_property} [] .
  }}"""

        elif grouping == self.GROUP_MAPPING.UNKNOWN_VALUE:
            query += f"""
  ?entity wdt:{self.grouping_property} ?grouping.
  FILTER wikibase:isSomeValue(?grouping)."""

        elif self.grouping_type == GroupingType.YEAR:
            query += f"""
  ?entity wdt:{self.grouping_property} ?date.
  BIND(YEAR(?date) as ?year).
  FILTER(?year = {grouping})."""

        else:
            query += f"""
  ?entity wdt:{self.grouping_property} wd:{grouping} ."""

        query += column.get_filter_for_positive_query()
        query += """}
"""
        return query

    def get_query_for_items_for_property_negative(self, column, grouping):
        column_key = column.get_key()
        query = f"""
SELECT DISTINCT ?entity ?entityLabel WHERE {{
  ?entity {self.selector_sparql} ."""

        if grouping == self.GROUP_MAPPING.TOTALS:
            query += """
  MINUS {"""

        elif grouping == self.GROUP_MAPPING.NO_GROUPING:
            query += f"""
  MINUS {{
    {{?entity wdt:{self.grouping_property} [] .}} UNION"""

        elif grouping == self.GROUP_MAPPING.UNKNOWN_VALUE:
            query += f"""
  ?entity wdt:{self.grouping_property} ?grouping.
  FILTER wikibase:isSomeValue(?grouping).
  MINUS {{"""

        elif self.grouping_type == GroupingType.YEAR:
            query += f"""
  ?entity wdt:{self.grouping_property} ?date.
  BIND(YEAR(?date) as ?year).
  FILTER(?year = {grouping}).
  MINUS {{"""

        else:
            query += f"""
  ?entity wdt:{self.grouping_property} wd:{grouping} .
  MINUS {{"""

        query += column.get_filter_for_negative_query()
        query += """}
"""
        return query

    def get_totals_no_grouping(self):
        query = f"""
SELECT (COUNT(*) as ?count) WHERE {{
  ?entity {self.selector_sparql}
  MINUS {{ ?entity wdt:{self.grouping_property} _:b28. }}
}}
"""
        return self._get_count_from_sparql(query)

    def get_totals(self):
        query = f"""
SELECT (COUNT(*) as ?count) WHERE {{
  ?entity {self.selector_sparql}
}}
"""
        return self._get_count_from_sparql(query)

    @staticmethod
    @statsd.timer('property_statistics.sparql.count')
    def _get_count_from_sparql(query):
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)
        if not queryresult:
            raise QueryException("No result when running a SPARQL query.", query=query)

        return int(queryresult[0].get('count'))

    @statsd.timer('property_statistics.sparql.grouping_counts')
    def _get_grouping_counts_from_sparql(self, query):
        result = collections.OrderedDict()
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)
        if not queryresult:
            return None
        for resultitem in queryresult:

            if not resultitem.get('grouping') or resultitem.get('grouping').startswith(self.UNKNOWN_VALUE_PREFIX):
                if self.GROUP_MAPPING.UNKNOWN_VALUE.name not in result.keys():
                    result[self.GROUP_MAPPING.UNKNOWN_VALUE.name] = 0
                result[self.GROUP_MAPPING.UNKNOWN_VALUE.name] += int(resultitem.get('count'))
            else:
                qid = resultitem.get('grouping').replace(u'http://www.wikidata.org/entity/', u'')
                result[qid] = int(resultitem.get('count'))

        return result

    @staticmethod
    def _get_percentage(count, total):
        if not count:
            return 0
        return round(1.0 * count / max(total, 1) * 100, 2)

    def get_header(self):
        text = u'{| class="wikitable sortable"\n'
        colspan = 3 if self.higher_grouping else 2
        text += f'! colspan="{colspan}" |Top groupings (Minimum {self.grouping_threshold} items)\n'
        text += f'! colspan="{len(self.columns)}"|Top Properties (used at least {self.property_threshold} times per grouping)\n'  # noqa
        text += u'|-\n'

        if self.higher_grouping:
            text += u'! \n'

        text += u'! Name\n'
        text += u'! Count\n'
        for column_entry in self.columns.values():
            text += column_entry.make_column_header()

        return text

    def make_stats_for_no_group(self):
        """
        Query the data for no_group, return the wikitext
        """
        text = u'|-\n'

        if self.higher_grouping:
            text += u'|\n'

        total_no_count = self.get_totals_no_grouping()
        text += u'| No grouping \n'
        text += f'| {total_no_count} \n'

        for column_entry in self.columns.values():
            column_count = self._get_count_from_sparql(column_entry.get_info_no_grouping_query(self))
            percentage = self._get_percentage(column_count, total_no_count)
            text += f'| {{{{{self.cell_template}|{percentage}|{column_count}|column={column_entry.get_title()}|grouping={self.GROUP_MAPPING.NO_GROUPING.value}}}}}\n'  # noqa

        return text

    def make_stats_for_one_grouping(self, grouping_object):
        """
        Query the data for one group, return the wikitext.
        """
        text = u'|-\n'
        grouping = grouping_object.title
        item_count = grouping_object.count

        text += grouping_object.format_header_cell(self.grouping_type)

        if self.grouping_link:
            try:
                group_item = pywikibot.ItemPage(self.repo, grouping)
                group_item.get()
                label = group_item.labels["en"]
            except (pywikibot.exceptions.InvalidTitleError, KeyError):
                logging.info(f"Could not retrieve label for {grouping}")
                label = grouping
            text += f'| [[{self.grouping_link}/{label}|{item_count}]] \n'
        else:
            text += f'| {item_count} \n'

        for column_entry in self.columns.values():
            text += grouping_object.format_cell(column_entry, self.cell_template)
        return text

    def make_footer(self):
        total_items = self.get_totals()
        text = u'|- class="sortbottom"\n|'
        if self.higher_grouping:
            text += u"|\n|"

        text += f'\'\'\'Totals\'\'\' <small>(all items)</small>:\n| {total_items}\n'
        for column_entry in self.columns.values():
            totalprop = self._get_count_from_sparql(column_entry.get_totals_query(self))
            percentage = self._get_percentage(totalprop, total_items)
            text += f'| {{{{{self.cell_template}|{percentage}|{totalprop}|column={column_entry.get_title()}}}}}\n'
        text += u'|}\n'
        return text

    @statsd.timer('property_statistics.processing')
    def retrieve_and_process_data(self):
        """
        Query the data, output wikitext
        """
        groupings = self.retrieve_data()
        text = self.process_data(groupings)
        return text

    def retrieve_data(self):
        logging.info("Retrieving grouping information...")

        try:
            groupings = self.get_grouping_information()
        except QueryException as e:
            logging.error('No groupings found.')
            raise e

        logging.info(f'Grouping retrieved: {len(groupings)}')

        for (column_entry_key, column_entry) in self.columns.items():
            data = self._get_grouping_counts_from_sparql(column_entry.get_info_query(self))
            for (grouping_item, value) in data.items():
                grouping = groupings.get(grouping_item)
                if grouping:
                    grouping.cells[column_entry_key] = value
                else:
                    logging.debug(f'Discarding data on {grouping_item}, not in the groupings')

        return groupings

    def process_data(self, groupings):
        text = self.get_header()

        for grouping in sorted(groupings.values(), key=lambda t: t.count, reverse=True):
            text += self.make_stats_for_one_grouping(grouping)

        if self.stats_for_no_group:
            text += self.make_stats_for_no_group()

        text += self.make_footer()

        return text


def main(*args):
    """
    Main function.
    """
    columns = [
        ColumnMaker.make('P21', None),
        ColumnMaker.make('P19', None),
        ColumnMaker.make('Lde', None),
        ColumnMaker.make('Dde', None),
    ]
    logging.info("Main function...")
    stats = PropertyStatistics(
        columns=columns,
        selector_sparql=u'wdt:P10241 wd:Q41960',
        grouping_property=u'P551',
        stats_for_no_group=True,
        grouping_threshold=5,
        property_threshold=1,
    )
    print(stats.retrieve_and_process_data())


if __name__ == "__main__":
    main()
