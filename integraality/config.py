"""The assembled dashboard configuration as a single typed object.

ParsedConfig is the output of ConfigAssembler.parse_config: one frozen value
carrying the PropertyStatistics inputs, the grouping_link_mode, and the
resolution-independent facts the config-persistence feature hashes.
"""

from dataclasses import dataclass, field, replace

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
    # --- resolution-independent facts preserved for the config hash / facets ---
    # The RAW grouping params (verbatim authored strings, NOT the
    # parsed/expanded predicate) and the PRE-expansion authored column keys.
    # Captured at parse time so neither assembly nor column-source expansion can
    # shift the hash input; this is what lets the live writer and the offline
    # backfiller compute identical hashes for the same authored config.
    raw_grouping_property: str | None = None
    raw_groupings: str | None = None
    authored_column_keys: tuple[str, ...] = field(default_factory=tuple)

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

        ``authored_column_keys`` is intentionally NOT replaced -- it pins the
        pre-expansion hash input through source expansion.
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
