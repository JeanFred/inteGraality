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
from line import (
    NoGroupGrouping,
    PropertyGrouping,
    TotalsGrouping,
    UnknownValueGrouping,
    YearGrouping,
)
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

    GROUP_MAPPING = Enum(
        "GROUP_MAPPING",
        {
            "NO_GROUPING": "None",
            "TOTALS": "",
            "UNKNOWN_VALUE": "{{int:wikibase-snakview-variations-somevalue-label}}",
        },
    )

    def __init__(
        self,
        selector_sparql,
        columns,
        grouping_property,
        grouping_type=None,
        higher_grouping=None,
        higher_grouping_type=None,
        stats_for_no_group=False,
        grouping_link=None,
        grouping_threshold=20,
        property_threshold=0,
    ):
        """
        Set what to work on and other variables here.
        """
        site = pywikibot.Site("en", "wikipedia")
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
        self.cell_template = "Integraality cell"

    @statsd.timer("property_statistics.sparql.groupings")
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
                    query=query,
                )

        except pywikibot.exceptions.TimeoutError:
            raise QueryException(
                "The Wikidata Query Service timed out when fetching groupings."
                "You might be trying to do something too expensive."
                "Please investigate the 'all groupings' debug query in the dashboard header.",
                query=query,
            )

        unknown_value_count = 0

        for resultitem in queryresult:
            if not resultitem.get("grouping") or resultitem.get("grouping").startswith(
                self.UNKNOWN_VALUE_PREFIX
            ):
                unknown_value_count += int(resultitem.get("count"))

            else:
                qid = resultitem.get("grouping").replace(
                    "http://www.wikidata.org/entity/", ""
                )
                if self.higher_grouping:
                    value = resultitem.get("higher_grouping")
                    if value:
                        value = value.replace("http://www.wikidata.org/entity/", "")
                    else:
                        value = ""
                    higher_grouping = value
                else:
                    higher_grouping = None
                if self.grouping_type == GroupingType.YEAR:
                    line_type = YearGrouping
                else:
                    line_type = PropertyGrouping
                property_grouping = line_type(
                    title=qid,
                    count=int(resultitem.get("count")),
                    higher_grouping=higher_grouping,
                )
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
    @statsd.timer("property_statistics.sparql.count")
    def _get_count_from_sparql(query):
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)
        if not queryresult:
            raise QueryException("No result when running a SPARQL query.", query=query)

        return int(queryresult[0].get("count"))

    @statsd.timer("property_statistics.sparql.grouping_counts")
    def _get_grouping_counts_from_sparql(self, query):
        result = collections.OrderedDict()
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)
        if not queryresult:
            return None
        for resultitem in queryresult:
            if not resultitem.get("grouping") or resultitem.get("grouping").startswith(
                self.UNKNOWN_VALUE_PREFIX
            ):
                if self.GROUP_MAPPING.UNKNOWN_VALUE.name not in result.keys():
                    result[self.GROUP_MAPPING.UNKNOWN_VALUE.name] = 0
                result[self.GROUP_MAPPING.UNKNOWN_VALUE.name] += int(
                    resultitem.get("count")
                )
            else:
                qid = resultitem.get("grouping").replace(
                    "http://www.wikidata.org/entity/", ""
                )
                result[qid] = int(resultitem.get("count"))

        return result

    def get_header(self):
        text = '{| class="wikitable sortable"\n'
        colspan = 3 if self.higher_grouping else 2
        text += f'! colspan="{colspan}" |Top groupings (Minimum {self.grouping_threshold} items)\n'
        text += f'! colspan="{len(self.columns)}"|Top Properties (used at least {self.property_threshold} times per grouping)\n'  # noqa
        text += "|-\n"

        if self.higher_grouping:
            text += "! \n"

        text += "! Name\n"
        text += "! Count\n"
        for column_entry in self.columns.values():
            text += column_entry.make_column_header()

        return text

    def make_stats_for_no_group(self):
        """
        Query the data for no_group, return the wikitext
        """
        count = self.get_totals_no_grouping()
        grouping_object = NoGroupGrouping(
            count=count, higher_grouping=self.higher_grouping
        )

        for column_entry_key, column_entry in self.columns.items():
            value = self._get_count_from_sparql(
                column_entry.get_info_no_grouping_query(self)
            )
            grouping_object.cells[column_entry_key] = value

        return self.format_stats_for_one_grouping(grouping_object)

    def format_stats_for_one_grouping(self, grouping_object):
        """
        Query the data for one group, return the wikitext.
        """
        text = grouping_object.row_opener()

        text += grouping_object.format_header_cell(self.grouping_type)
        text += grouping_object.format_count_cell(self.grouping_link, self.repo)
        for column_entry in self.columns.values():
            text += grouping_object.format_cell(column_entry, self.cell_template)
        return text

    def make_totals(self):
        count = self.get_totals()
        grouping_object = TotalsGrouping(
            count=count, title="", higher_grouping=self.higher_grouping
        )

        for column_entry_key, column_entry in self.columns.items():
            value = self._get_count_from_sparql(column_entry.get_totals_query(self))
            grouping_object.cells[column_entry_key] = value

        return self.format_stats_for_one_grouping(grouping_object)

    @statsd.timer("property_statistics.processing")
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
            logging.error("No groupings found.")
            raise e

        logging.info(f"Grouping retrieved: {len(groupings)}")

        for column_entry_key, column_entry in self.columns.items():
            data = self._get_grouping_counts_from_sparql(
                column_entry.get_info_query(self)
            )
            for grouping_item, value in data.items():
                grouping = groupings.get(grouping_item)
                if grouping:
                    grouping.cells[column_entry_key] = value
                else:
                    logging.debug(
                        f"Discarding data on {grouping_item}, not in the groupings"
                    )

        return groupings

    def process_data(self, groupings):
        text = self.get_header()

        for grouping in sorted(groupings.values(), key=lambda t: t.count, reverse=True):
            text += self.format_stats_for_one_grouping(grouping)

        if self.stats_for_no_group:
            text += self.make_stats_for_no_group()

        text += self.make_totals()
        text += "|}\n"

        return text


def main(*args):
    """
    Main function.
    """
    columns = [
        ColumnMaker.make("P21", None),
        ColumnMaker.make("P19", None),
        ColumnMaker.make("Lde", None),
        ColumnMaker.make("Dde", None),
    ]
    logging.info("Main function...")
    stats = PropertyStatistics(
        columns=columns,
        selector_sparql="wdt:P10241 wd:Q41960",
        grouping_property="P551",
        stats_for_no_group=True,
        grouping_threshold=5,
        property_threshold=1,
    )
    print(stats.retrieve_and_process_data())


if __name__ == "__main__":
    main()
