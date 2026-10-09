"""Tests for ParsedConfig (config.py)."""

import unittest

from ..column import PropertyColumn, PropertySourceColumn
from ..config import ParsedConfig
from ..grouping import GroupingConfiguration, ItemGroupingType


class _FakeResolver:
    """Expands the single source placeholder into two concrete columns."""

    def resolve_placeholders(self, columns):
        expanded = []
        for column in columns:
            if isinstance(column, PropertySourceColumn):
                expanded.extend(
                    [PropertyColumn(property="P18"), PropertyColumn(property="P569")]
                )
            else:
                expanded.append(column)
        return expanded


class TestResolvedPreservesAuthoredKeys(unittest.TestCase):
    def _config(self):
        return ParsedConfig(
            selector_sparql="wdt:P31 wd:Q5",
            columns=(PropertySourceColumn(source_property="P1963", source_item="Q5"),),
            grouping_configuration=GroupingConfiguration(
                predicate="wdt:P21", grouping_type=ItemGroupingType()
            ),
            sparql_query_engine=object(),
            authored_column_keys=("P1963(Q5)",),
        )

    def test_resolved_expands_columns_but_keeps_authored_keys(self):
        # The load-bearing invariant: source expansion must not shift the
        # pre-expansion keys the config hash is defined over.
        resolved = self._config().resolved(_FakeResolver())
        self.assertEqual(resolved.authored_column_keys, ("P1963(Q5)",))
        self.assertEqual(len(resolved.columns), 2)  # expansion happened
        self.assertEqual([c.get_key() for c in resolved.columns], ["P18", "P569"])
