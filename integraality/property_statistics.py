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
from grouping import ItemGroupingConfiguration
from line import (
    ItemGrouping,
    NoGroupGrouping,
    SitelinkGrouping,
    TotalsGrouping,
    UnknownValueGrouping,
    YearGrouping,
)
from sparql_utils import UNKNOWN_VALUE_PREFIX, QueryException


class PropertyStatistics:
    """
    Generate statitics

    """

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
        grouping_configuration,
        grouping_type=None,
        higher_grouping_type=None,
        stats_for_no_group=False,
        property_threshold=0,
    ):
        """
        Set what to work on and other variables here.
        """
        self.columns = {column.get_key(): column for column in columns}
        self.grouping_configuration = grouping_configuration
        if grouping_type:
            self.grouping_type = GroupingType(grouping_type)
        else:
            self.grouping_type = None
        self.higher_grouping_type = higher_grouping_type
        self.selector_sparql = selector_sparql
        self.stats_for_no_group = stats_for_no_group
        self.property_threshold = property_threshold

        self.cell_template = "Integraality cell"

    def get_grouping_information(self):
        """
        Get all groupings and their counts.

        :return: List of Grouping objects
        """
        return self.grouping_configuration.get_grouping_information(
            self.selector_sparql
        )

    def get_query_for_items_for_property_positive(self, column, grouping):
        grouping_predicate = self.grouping_configuration.get_predicate()

        if grouping == self.GROUP_MAPPING.TOTALS:
            line = TotalsGrouping(None)
        elif grouping == self.GROUP_MAPPING.NO_GROUPING:
            line = NoGroupGrouping(None)
        elif grouping == self.GROUP_MAPPING.UNKNOWN_VALUE:
            line = UnknownValueGrouping(None)
        elif self.grouping_type == GroupingType.YEAR:
            line = YearGrouping(None)
        elif grouping.startswith("https://"):
            line = SitelinkGrouping(None)
        else:
            line = ItemGrouping(None)

        query = "\n"
        query += line.postive_query(self.selector_sparql, grouping_predicate, grouping)
        query += column.get_filter_for_positive_query()
        query += column.get_service_wikibase_label()
        query += """}
"""
        return query

    def get_query_for_items_for_property_negative(self, column, grouping):
        grouping_predicate = self.grouping_configuration.get_predicate()

        if grouping == self.GROUP_MAPPING.TOTALS:
            line = TotalsGrouping(None)
        elif grouping == self.GROUP_MAPPING.NO_GROUPING:
            line = NoGroupGrouping(None)
        elif grouping == self.GROUP_MAPPING.UNKNOWN_VALUE:
            line = UnknownValueGrouping(None)
        elif self.grouping_type == GroupingType.YEAR:
            line = YearGrouping(None)
        elif grouping.startswith("https://"):
            line = SitelinkGrouping(None)
        else:
            line = ItemGrouping(None)

        query = "\n"
        query += line.negative_query(self.selector_sparql, grouping_predicate, grouping)
        query += column.get_filter_for_negative_query()
        query += column.get_service_wikibase_label()
        query += """}
"""
        return query

    def get_totals_no_grouping(self):
        grouping_predicate = self.grouping_configuration.get_predicate()
        query = f"""
SELECT (COUNT(*) as ?count) WHERE {{
  ?entity {self.selector_sparql}
  MINUS {{ ?entity {grouping_predicate} _:b28. }}
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
    def _get_count_from_sparql(query):
        try:
            sq = pywikibot.data.sparql.SparqlQuery()
            queryresult = sq.select(query)
            if not queryresult:
                raise QueryException(
                    "No result when running a SPARQL query.", query=query
                )

        except (pywikibot.exceptions.TimeoutError, pywikibot.exceptions.ServerError):
            raise QueryException(
                "The Wikidata Query Service timed out when running a SPARQL query."
                "You might be trying to do something too expensive.",
                query=query,
            )

        return int(queryresult[0].get("count"))

    def _get_grouping_counts_from_sparql(self, query):
        result = collections.OrderedDict()
        try:
            sq = pywikibot.data.sparql.SparqlQuery()
            queryresult = sq.select(query)
            if not queryresult:
                return None

        except (pywikibot.exceptions.TimeoutError, pywikibot.exceptions.ServerError):
            raise QueryException(
                "The Wikidata Query Service timed out when running a SPARQL query."
                "You might be trying to do something too expensive.",
                query=query,
            )

        for resultitem in queryresult:
            if not resultitem.get("grouping") or resultitem.get("grouping").startswith(
                UNKNOWN_VALUE_PREFIX
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
        colspan = 3 if self.grouping_configuration.higher_grouping else 2
        text += f'! colspan="{colspan}" |Top groupings (Minimum {self.grouping_configuration.grouping_threshold} items)\n'
        text += f'! colspan="{len(self.columns)}"|Top Properties (used at least {self.property_threshold} times per grouping)\n'  # noqa
        text += "|-\n"

        if self.grouping_configuration.higher_grouping:
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
            count=count, higher_grouping=self.grouping_configuration.higher_grouping
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

        text += grouping_object.format_header_cell(
            self.grouping_configuration, self.grouping_type
        )
        text += grouping_object.format_count_cell()
        for column_entry in self.columns.values():
            text += grouping_object.format_cell(column_entry, self.cell_template)
        return text

    def make_totals(self):
        count = self.get_totals()
        grouping_object = TotalsGrouping(
            count=count,
            title="",
            higher_grouping=self.grouping_configuration.higher_grouping,
        )

        for column_entry_key, column_entry in self.columns.items():
            value = self._get_count_from_sparql(column_entry.get_totals_query(self))
            grouping_object.cells[column_entry_key] = value

        return self.format_stats_for_one_grouping(grouping_object)

    def retrieve_and_process_data(self):
        """
        Query the data, output wikitext
        """
        groupings = self.retrieve_data()
        text = self.process_data(groupings)
        return text

    def populate_groupings(self, groupings):
        for column_entry_key, column_entry in self.columns.items():
            data = self._get_grouping_counts_from_sparql(
                column_entry.get_info_query(self)
            )
            if not data:
                continue
            for grouping_item, value in data.items():
                grouping = groupings.get(grouping_item)
                if grouping:
                    grouping.cells[column_entry_key] = value
                else:
                    logging.debug(
                        f"Discarding data on {grouping_item}, not in the groupings"
                    )
        return groupings

    def retrieve_data(self):
        logging.info("Retrieving grouping information...")

        try:
            groupings = self.get_grouping_information()
        except QueryException as e:
            logging.error("No groupings found.")
            raise e

        logging.info(f"Grouping retrieved: {len(groupings)}")
        groupings = self.populate_groupings(groupings)
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
        grouping_configuration=ItemGroupingConfiguration(
            property="P551", grouping_threshold=5
        ),
        stats_for_no_group=True,
        property_threshold=1,
    )
    print(stats.retrieve_and_process_data())


if __name__ == "__main__":
    main()
