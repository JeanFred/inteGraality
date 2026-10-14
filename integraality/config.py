"""The assembled dashboard configuration as a single typed object."""

from dataclasses import dataclass, replace

from .column import AbstractColumn, PropertySourceColumn
from .grouping import GroupingConfiguration
from .sparql_utils import SparqlQueryEngine


@dataclass(frozen=True)
class ParsedConfig:
    # --- PropertyStatistics inputs (fed via stats_kwargs) ---
    selector_sparql: str
    columns: tuple[AbstractColumn | PropertySourceColumn, ...]
    grouping_configuration: GroupingConfiguration
    sparql_query_engine: SparqlQueryEngine
    row_no_group: bool = False
    row_totals: bool = True
    # --- parsed extra, consumed by the processor / page creator ---
    grouping_link_mode: str = "link"

    def stats_kwargs(self):
        """The kwargs for PropertyStatistics (no splat of the whole object)."""
        return {
            "selector_sparql": self.selector_sparql,
            "columns": list(self.columns),
            "grouping_configuration": self.grouping_configuration,
            "sparql_query_engine": self.sparql_query_engine,
            "row_no_group": self.row_no_group,
            "row_totals": self.row_totals,
        }

    def resolved(self, column_resolver):
        """Return a new ParsedConfig with the grouping type detected and column
        sources expanded. Value-returning: pure with respect to self.
        """
        grouping_configuration = self.grouping_configuration.with_resolved_type(
            self.selector_sparql, self.sparql_query_engine
        )
        columns = tuple(column_resolver.resolve_placeholders(list(self.columns)))
        return replace(
            self,
            grouping_configuration=grouping_configuration,
            columns=columns,
        )
