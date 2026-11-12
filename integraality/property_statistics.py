"""Core logic — builds SPARQL queries, processes results."""

import collections
import logging

from .column import ColumnMaker, PropertySourceColumn, UnresolvedColumnSourceException
from .error_category import ErrorCategory
from .grouping import (
    EmptyGroupingException,
    GroupingConfiguration,
    ItemGroupingType,
)
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
    expand_select_vars,
    get_labels_for_select_vars,
)

logger = logging.getLogger("integraality.update")


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
        row_no_group=False,
        row_totals=True,
        sparql_query_engine=None,
    ):
        """
        Set what to work on and other variables here.
        """
        if sparql_query_engine is None:
            sparql_query_engine = WdqsSparqlQueryEngine()
        unresolved = [c for c in columns if isinstance(c, PropertySourceColumn)]
        if unresolved:
            raise UnresolvedColumnSourceException(
                "Column source(s) reached PropertyStatistics unresolved: "
                f"{', '.join(c.get_key() for c in unresolved)}. "
                "They must be expanded via ColumnSourceResolver before use."
            )
        self.columns = {column.get_key(): column for column in columns}
        self.grouping_configuration = grouping_configuration
        self.selector_sparql = selector_sparql
        self.row_no_group = row_no_group
        self.row_totals = row_totals
        self.sparql_query_engine = sparql_query_engine

        # Safety net for stats objects constructed directly (tests, __main__);
        # the processor already resolves before constructing.
        self.grouping_configuration = self.grouping_configuration.with_resolved_type(
            selector_sparql, sparql_query_engine
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

    def get_queries_for_column(self, column_key, grouping):
        column = self.columns.get(column_key)
        return {
            "column": column,
            "positive_query": self.get_query_for_items_for_property_positive(
                column, grouping
            ),
            "negative_query": self.get_query_for_items_for_property_negative(
                column, grouping
            ),
            "formatted_predicate": self.grouping_configuration.format_predicate_html(),
        }

    def get_query_for_items_for_property_positive(self, column, grouping):
        grouping_predicate = self.grouping_configuration.get_predicate()
        line, grouping = self._make_line_for_grouping(grouping)

        column_filter, select_vars = column.get_filter_for_positive_query()
        return self._build_drilldown_query(
            line.postive_query,
            select_vars,
            column_filter,
            grouping_predicate,
            grouping,
            line,
        )

    def get_query_for_items_for_property_negative(self, column, grouping):
        grouping_predicate = self.grouping_configuration.get_predicate()
        line, grouping = self._make_line_for_grouping(grouping)

        column_filter, select_vars = column.get_filter_for_negative_query()
        return self._build_drilldown_query(
            line.negative_query,
            select_vars,
            column_filter,
            grouping_predicate,
            grouping,
            line,
        )

    def _build_drilldown_query(
        self,
        query_fn,
        select_vars,
        column_filter,
        grouping_predicate,
        grouping,
        line,
    ):
        """Build a drilldown query with labels resolved in an outer query.

        Wraps the entity-selection logic in a subquery so that SPARQL
        optimizers resolve the complex pattern first, then join against
        the rdfs:label graph on a small result set.
        """
        inner_select_clause = " ".join(select_vars)
        outer_select_clause = expand_select_vars(select_vars)

        # Inner subquery: entity selection without labels
        inner = query_fn(
            self.selector_sparql, inner_select_clause, grouping_predicate, grouping
        )
        inner += line.grouping_bind(grouping)
        inner += column_filter
        inner += "}"

        # Outer query: label resolution on the small result set
        query = "\n"
        query += f"SELECT {outer_select_clause} WHERE {{\n"
        query += "  {\n"
        for inner_line in inner.split("\n"):
            query += f"  {inner_line}\n"
        query += "  }\n"
        query += get_labels_for_select_vars(select_vars)
        query += "}\n"
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
        logger.info(
            "Querying count of items without grouping...",
            extra={"query": query, "step_key": "nogroup_count"},
        )
        result = self._get_count_from_sparql(query)
        logger.info(
            "Count of items without grouping done",
            extra={"phase": "end", "step_key": "nogroup_count"},
        )
        return result

    def get_totals(self):
        query = f"""
SELECT (COUNT(*) as ?count) WHERE {{
  ?entity {self.selector_sparql}
}}
"""
        logger.info(
            "Querying total item count...",
            extra={"query": query, "step_key": "totals_count"},
        )
        result = self._get_count_from_sparql(query)
        logger.info(
            "Total item count done",
            extra={"phase": "end", "step_key": "totals_count"},
        )
        return result

    def _get_count_from_sparql(self, query):
        queryresult = self.sparql_query_engine.select(query)
        if not queryresult:
            # A well-formed COUNT returns a row with 0; no row at all is
            # unexpected, so the neutral ERROR category (base QueryException).
            raise QueryException("No result when running a SPARQL query.", query=query)

        return int(queryresult[0].get("count"))

    def _get_grouping_counts_from_sparql(self, query):
        result = collections.OrderedDict()
        queryresult = self.sparql_query_engine.select(query)
        if not queryresult:
            return None

        for resultitem in queryresult:
            if not resultitem.get("grouping") or resultitem.get("grouping").startswith(
                UNKNOWN_VALUE_PREFIX
            ):
                if UnknownValueGrouping.MARKER not in result:
                    result[UnknownValueGrouping.MARKER] = 0
                result[UnknownValueGrouping.MARKER] += int(resultitem.get("count"))
            else:
                qid = resultitem.get("grouping").replace(
                    "http://www.wikidata.org/entity/", ""
                )
                result[qid] = int(resultitem.get("count"))

        return result

    @staticmethod
    def _make_column_task(col, idx, total, step_key, query_fn, handle_result):
        """Return a callable that runs query_fn(col) and passes the result to handle_result."""

        def task():
            query = query_fn(col)
            logger.info(
                f"Querying {step_key}... ({idx}/{total})",
                extra={"query": query, "step_key": step_key},
            )
            handle_result(query)
            logger.info(
                f"{step_key} done ({idx}/{total})",
                extra={"phase": "end", "step_key": step_key},
            )

        return task

    def _make_special_row(self, grouping_class, count_fn, column_query_fn, step_label):
        """Build a special grouping row object and return it with its per-column tasks."""
        # count_fn runs eagerly: the grouping object must exist before column
        # tasks can write into its cells. Column queries are deferred into tasks
        # for _run_query_queue.
        count = count_fn()
        grouping_object = grouping_class(
            count=count, higher_grouping=self.grouping_configuration.higher_grouping
        )
        column_keys = list(self.columns.keys())
        total = len(column_keys)
        tasks = []
        for i, (column_entry_key, column_entry) in enumerate(self.columns.items(), 1):
            step_key = f"{step_label}_{column_entry_key}"

            def handle_result(query, key=column_entry_key):
                value = self._get_count_from_sparql(query)
                grouping_object.cells[key] = value

            tasks.append(
                self._make_column_task(
                    col=column_entry,
                    idx=i,
                    total=total,
                    step_key=step_key,
                    query_fn=column_query_fn,
                    handle_result=handle_result,
                )
            )
        return grouping_object, tasks

    def make_stats_for_no_group(self):
        """Build the no-group row: items that don't match any grouping."""
        return self._make_special_row(
            grouping_class=NoGroupGrouping,
            count_fn=self.get_totals_no_grouping,
            column_query_fn=lambda col: col.get_info_no_grouping_query(self),
            step_label="no-group",
        )

    def make_totals(self):
        """Build the totals row: coverage counts across all items in scope."""
        return self._make_special_row(
            grouping_class=TotalsGrouping,
            count_fn=self.get_totals,
            column_query_fn=lambda col: col.get_totals_query(self),
            step_label="totals",
        )

    def _run_query_queue(self, tasks, max_passes=3):
        """Run tasks, retrying transiently-failed ones up to max_passes times."""
        remaining = list(tasks)
        for _ in range(max_passes):
            if not remaining:
                break
            next_round = []
            for task in remaining:
                try:
                    task()
                except QueryException as e:
                    if e.error_category in (
                        ErrorCategory.TRANSIENT,
                        ErrorCategory.TIMEOUT,
                    ):
                        next_round.append(task)
                    else:
                        logger.warning("Giving up on task: %s", e)
            remaining = next_round

    def _make_groupings_tasks(self, groupings):
        """Return per-column tasks that populate cells across all grouping objects."""
        column_keys = list(self.columns.keys())
        total = len(column_keys)
        tasks = []
        for i, (column_entry_key, column_entry) in enumerate(self.columns.items(), 1):
            step_key = f"columns_{column_entry_key}"

            def handle_result(query, key=column_entry_key):
                data = self._get_grouping_counts_from_sparql(query)
                if not data:
                    return
                for grouping_item, value in data.items():
                    grouping = groupings.get(grouping_item)
                    if grouping:
                        grouping.cells[key] = value
                    else:
                        logger.debug(
                            f"Discarding data on {grouping_item}, not in the groupings"
                        )

            tasks.append(
                self._make_column_task(
                    col=column_entry,
                    idx=i,
                    total=total,
                    step_key=step_key,
                    query_fn=lambda col: col.get_info_query(self),
                    handle_result=handle_result,
                )
            )
        return tasks

    def populate_groupings(self, groupings):
        """Run per-column queries and populate grouping cells."""
        if groupings is None:
            return None
        self._run_query_queue(self._make_groupings_tasks(groupings))
        return groupings

    def retrieve_data(self):
        grouping_query = self.grouping_configuration.get_grouping_information_query(
            self.selector_sparql
        )
        logger.info(
            "Retrieving grouping information...",
            extra={"query": grouping_query, "step_key": "groupings"},
        )

        try:
            groupings = self.get_grouping_information()
        except EmptyGroupingException:
            logger.error("No groupings found.")
            raise
        except QueryException as e:
            logger.error("Could not retrieve groupings: %s", e)
            raise

        logger.info(
            f"Retrieved {len(groupings)} groupings",
            extra={"phase": "end", "step_key": "groupings"},
        )
        all_tasks = self._make_groupings_tasks(groupings)

        if self.row_no_group:
            logger.info(
                "Computing stats for items without grouping...",
                extra={"step_key": "nogroup"},
            )
            no_group, tasks = self.make_stats_for_no_group()
            all_tasks.extend(tasks)
            groupings[NoGroupGrouping.MARKER] = no_group
            logger.info(
                "Computing stats for items without grouping done",
                extra={"phase": "end", "step_key": "nogroup"},
            )

        if self.row_totals:
            logger.info("Computing totals...", extra={"step_key": "totals"})
            totals, tasks = self.make_totals()
            all_tasks.extend(tasks)
            groupings[TotalsGrouping.MARKER] = totals
            logger.info(
                "Computing totals done", extra={"phase": "end", "step_key": "totals"}
            )

        self._run_query_queue(all_tasks)
        groupings = self.grouping_configuration.post_process(groupings)

        return groupings

    def prepare_report_groupings(self, groupings):
        """Sort groupings by priority then count − special rows always last."""
        return sorted(
            groupings.values(),
            key=lambda t: (t.sort_priority, -t.count, t.get_key()),
        )

    def build_formatter(self, formatter_class=ResultsFormatter, **kwargs):
        return formatter_class(
            columns=self.columns,
            grouping_configuration=self.grouping_configuration,
            **kwargs,
        )

    @staticmethod
    def get_entity_total(report_groupings):
        """Return the totals-row count (the denominator population) from the
        report groupings, or None when the dashboard has no totals row."""
        return next(
            (g.count for g in report_groupings if isinstance(g, TotalsGrouping)),
            None,
        )


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
    logger.info("Main function...")
    stats = PropertyStatistics(
        columns=columns,
        selector_sparql="wdt:P10241 wd:Q41960",
        grouping_configuration=GroupingConfiguration(
            predicate="wdt:P551", grouping_type=ItemGroupingType(), grouping_threshold=5
        ),
        row_no_group=True,
    )
    groupings = stats.retrieve_data()
    report_groupings = stats.prepare_report_groupings(groupings)
    formatter = stats.build_formatter()
    print(formatter.format_report(report_groupings))


if __name__ == "__main__":
    main()
