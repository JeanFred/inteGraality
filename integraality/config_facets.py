"""Extract persistable config facets from an assembled config.

Pure and DB-free, so the live writer, snapshot and backfiller all persist
identical facets (and compute identical hashes).
"""

import re
from dataclasses import dataclass, field

from .column import PropertySourceColumn, split_value_traversal
from .config_hash import canonical_token_bag, compute_config_hash
from .grouping import (
    ItemGroupingType,
    SitelinkGroupingType,
    YearGroupingType,
)

# bare P/Q id tokens inside the selector, for the selector_mentions bag.
_PQ_ID_RE = re.compile(r"\b([PQ]\d+)\b")

# A simple grouping predicate (wdt:Pnnn) exposes a plain grouping_property;
# anything compound (paths, ^schema:about) does not -- NULL, syntactically.
_SIMPLE_PREDICATE_RE = re.compile(r"^wdt:(P\d+)$")

_GROUPING_TYPE_TOKEN = {
    ItemGroupingType: "item",
    YearGroupingType: "year",
    SitelinkGroupingType: "sitelink",
}


@dataclass(frozen=True)
class ColumnFacets:
    """One expanded column's persistable facets (one DB row)."""

    position: int
    column_type: str
    raw_key: str
    property_id: str | None = None
    qualifier_id: str | None = None
    value: str | None = None
    value_item: str | None = None
    value_traversal: str | None = None
    reference_check_kind: str | None = None
    reference_check_tokens: str | None = None
    source_property: str | None = None
    source_item: str | None = None
    language: str | None = None
    project: str | None = None


@dataclass(frozen=True)
class ConfigFacets:
    """Everything needed to persist one configuration row + its columns."""

    config_hash: str
    grouping_predicate: str
    grouping_property: str | None
    grouping_type: str | None
    grouping_threshold: int
    higher_grouping: str | None
    selector_sparql: str
    selector_mentions: str | None
    row_totals: bool
    row_no_group: bool
    grouping_link_mode: str
    explicit_groupings: str | None
    columns: list[ColumnFacets] = field(default_factory=list)


def grouping_property_from_predicate(predicate):
    """Plain P-id for a simple wdt:Pnnn predicate, else None (no sniffing)."""
    match = _SIMPLE_PREDICATE_RE.match(predicate or "")
    return match.group(1) if match else None


def grouping_type_token(grouping_type):
    """Token for a resolved grouping-type instance, or None if unresolved."""
    if grouping_type is None:
        return None
    return _GROUPING_TYPE_TOKEN.get(type(grouping_type))


def selector_mentions(selector_sparql):
    """Comma-padded bag of the P/Q ids mentioned in the selector."""
    return canonical_token_bag(_PQ_ID_RE.findall(selector_sparql or ""))


def explicit_groupings_bag(raw_groupings):
    """Comma-padded bag of the RAW groupings tokens (syntactic), or None."""
    if not raw_groupings:
        return None
    return canonical_token_bag(raw_groupings.split(","))


def _value_facets(column):
    """(value, value_item, value_traversal) for a value-scoped column."""
    value = column.value
    if not value:
        return {}
    bare, traversal = split_value_traversal(value)
    return {
        "value": value,
        "value_item": bare if bare and bare.startswith("Q") else None,
        "value_traversal": traversal,
    }


def _column_facets(position, column):
    # Dispatch on get_type_name(); each branch reads its class's attributes
    # directly, so a drifting column surfaces as an error, not a silent NULL.
    column_type = column.get_type_name()
    common = {
        "position": position,
        "column_type": column_type,
        "raw_key": column.get_key(),
    }
    if column_type == "property":
        return ColumnFacets(
            **common,
            property_id=column.property,
            source_property=column.source_property,
            source_item=column.source_item,
            **_value_facets(column),
        )
    if column_type == "qualifier":
        return ColumnFacets(
            **common,
            property_id=column.property,
            qualifier_id=column.qualifier,
            source_property=column.source_property,
            source_item=column.source_item,
            **_value_facets(column),
        )
    if column_type == "reference":
        check = column.reference_check
        return ColumnFacets(
            **common,
            property_id=column.property,
            qualifier_id=column.qualifier,
            reference_check_kind=check.kind,
            reference_check_tokens=canonical_token_bag(check.reference_atoms()),
            source_property=column.source_property,
            source_item=column.source_item,
            **_value_facets(column),
        )
    if column_type in ("label", "description"):
        return ColumnFacets(**common, language=column.language)
    if column_type == "sitelink":
        return ColumnFacets(**common, project=column.project)
    raise ValueError(f"Unmappable column type for persistence: {column!r}")


def extract_column_facets(expanded_columns):
    """Build the ordered ColumnFacets rows from post-expansion columns."""
    return [
        _column_facets(position, column)
        for position, column in enumerate(expanded_columns)
    ]


def build_config_facets(parsed_config):
    """Assemble the ConfigFacets (hash + row values + column rows) from a config.

    Hash over the PRE-expansion authored column keys; rows over the
    post-expansion concrete columns (unexpandable sources contribute no row).
    """
    grouping_configuration = parsed_config.grouping_configuration
    threshold = grouping_configuration.grouping_threshold
    higher_grouping = grouping_configuration.higher_grouping
    config_hash = compute_config_hash(
        selector_sparql=parsed_config.selector_sparql,
        grouping_property=parsed_config.raw_grouping_property,
        grouping_threshold=threshold,
        higher_grouping=higher_grouping,
        groupings=parsed_config.raw_groupings,
        row_totals=parsed_config.row_totals,
        row_no_group=parsed_config.row_no_group,
        grouping_link_mode=parsed_config.grouping_link_mode,
        column_keys=list(parsed_config.authored_column_keys),
    )
    predicate = grouping_configuration.get_predicate()
    concrete_columns = [
        column
        for column in parsed_config.columns
        if not isinstance(column, PropertySourceColumn)
    ]
    return ConfigFacets(
        config_hash=config_hash,
        grouping_predicate=predicate,
        grouping_property=grouping_property_from_predicate(predicate),
        grouping_type=grouping_type_token(grouping_configuration.grouping_type),
        grouping_threshold=threshold,
        higher_grouping=higher_grouping,
        selector_sparql=parsed_config.selector_sparql,
        selector_mentions=selector_mentions(parsed_config.selector_sparql),
        row_totals=parsed_config.row_totals,
        row_no_group=parsed_config.row_no_group,
        grouping_link_mode=parsed_config.grouping_link_mode,
        explicit_groupings=explicit_groupings_bag(parsed_config.raw_groupings),
        columns=extract_column_facets(concrete_columns),
    )
