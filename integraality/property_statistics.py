#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Calculate and generate statistics

"""

import collections
import logging

from .column import ColumnMaker
from .grouping import GroupingConfiguration, ItemGroupingType
from .line import (
    NoGroupGrouping,
    TotalsGrouping,
    UnknownValueGrouping,
    YearGrouping,
)
from .results_formatter import ResultsFormatter
from .sparql_utils import (
    UNKNOWN_VALUE_PREFIX,
    QueryException,
    WdqsSparqlQueryEngine,
)


class PropertyStatistics:
    """
    Generate statitics

    """

    SPECIAL_GROUPINGS = (NoGroupGrouping, TotalsGrouping, UnknownValueGrouping)

    @classmethod
    def _find_special_grouping(cls, grouping_arg):
        for grouping_class in cls.SPECIAL_GROUPINGS:
            if grouping_arg == grouping_class.MARKER:
                return grouping_class
        return None

    def __init__(
        self,
        selector_sparql,
        columns,
        grouping_configuration,
        grouping_type=None,
        higher_grouping_type=None,
        stats_for_no_group=False,
        property_threshold=0,
        sparql_query_engine=WdqsSparqlQueryEngine(),
    ):
        """
        Set what to work on and other variables here.
        """
        self.columns = {column.get_key(): column for column in columns}
        self.grouping_configuration = grouping_configuration
        self.higher_grouping_type = higher_grouping_type
        self.selector_sparql = selector_sparql
        self.stats_for_no_group = stats_for_no_group
        self.property_threshold = property_threshold
        self.sparql_query_engine = sparql_query_engine

        self.grouping_configuration._resolve_type(selector_sparql, sparql_query_engine)
        self.formatter = ResultsFormatter(
            columns=self.columns,
            grouping_configuration=grouping_configuration,
            property_threshold=property_threshold,
        )

    def get_sparql_engine_name(self):
        return self.sparql_query_engine.name

    def get_grouping_information(self):
        """
        Get all groupings and their counts.

        :return: List of Grouping objects
        """
        return self.grouping_configuration.get_grouping_information(
            self.selector_sparql, self.sparql_query_engine
        )

    def get_query_for_items_for_property_positive(self, column, grouping):
        grouping_predicate = self.grouping_configuration.get_predicate()
        line, grouping = self._make_line_for_grouping(grouping)

        query = "\n"
        query += line.postive_query(self.selector_sparql, grouping_predicate, grouping)
        query += column.get_filter_for_positive_query()
        query += column.get_variable_labels_for_positive_query()
        query += """}
"""
        return query

    def get_query_for_items_for_property_negative(self, column, grouping):
        grouping_predicate = self.grouping_configuration.get_predicate()
        line, grouping = self._make_line_for_grouping(grouping)

        query = "\n"
        query += line.negative_query(self.selector_sparql, grouping_predicate, grouping)
        query += column.get_filter_for_negative_query()
        query += column.get_variable_labels_for_negative_query()
        query += """}
"""
        return query

    def _make_line_for_grouping(self, grouping):
        grouping_class = self._find_special_grouping(grouping)
        if grouping_class:
            return grouping_class(None), grouping
        line_type = self.grouping_configuration.line_type
        if line_type == YearGrouping and "/" in str(grouping):
            title, time_span = grouping.rsplit("/", 1)
            return YearGrouping(None, time_span=int(time_span)), title
        return line_type(None), grouping

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

    def _get_count_from_sparql(self, query):
        try:
            queryresult = self.sparql_query_engine.select(query)
            if not queryresult:
                raise QueryException(
                    "No result when running a SPARQL query.", query=query
                )

        except QueryException:
            raise

        return int(queryresult[0].get("count"))

    def _get_grouping_counts_from_sparql(self, query):
        result = collections.OrderedDict()
        try:
            queryresult = self.sparql_query_engine.select(query)
            if not queryresult:
                return None

        except QueryException:
            raise

        for resultitem in queryresult:
            if not resultitem.get("grouping") or resultitem.get("grouping").startswith(
                UNKNOWN_VALUE_PREFIX
            ):
                if UnknownValueGrouping.MARKER not in result.keys():
                    result[UnknownValueGrouping.MARKER] = 0
                result[UnknownValueGrouping.MARKER] += int(resultitem.get("count"))
            else:
                qid = resultitem.get("grouping").replace(
                    "http://www.wikidata.org/entity/", ""
                )
                result[qid] = int(resultitem.get("count"))

        return result

    def make_stats_for_no_group(self):
        """
        Query the data for no_group, return the grouping object.
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

        return grouping_object

    def make_totals(self):
        """
        Query the data for totals, return the grouping object.
        """
        count = self.get_totals()
        grouping_object = TotalsGrouping(
            count=count,
            higher_grouping=self.grouping_configuration.higher_grouping,
        )

        for column_entry_key, column_entry in self.columns.items():
            value = self._get_count_from_sparql(column_entry.get_totals_query(self))
            grouping_object.cells[column_entry_key] = value

        return grouping_object

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
        groupings = self.grouping_configuration.post_process(groupings)
        return groupings

    def process_data(self, groupings):
        sorted_groupings = sorted(
            groupings.values(), key=lambda t: t.count, reverse=True
        )

        if self.stats_for_no_group:
            sorted_groupings.append(self.make_stats_for_no_group())

        sorted_groupings.append(self.make_totals())

        return self.formatter.format_report(sorted_groupings)


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
        grouping_configuration=GroupingConfiguration(
            predicate="wdt:P551", grouping_type=ItemGroupingType(), grouping_threshold=5
        ),
        stats_for_no_group=True,
        property_threshold=1,
    )
    print(stats.retrieve_and_process_data())


if __name__ == "__main__":
    main()
