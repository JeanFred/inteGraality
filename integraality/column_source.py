"""Resolve PropertySourceColumn placeholders into concrete columns.

A dashboard may source its columns from the values of a property on an item,
e.g. "P1963(Q39715)" takes the properties listed via P1963 ("properties for
this type") on the lighthouse item. This module reads those values from the
wiki API, preserving their on-wiki order, and expands the placeholder into one
PropertyColumn per property value. Non-property values are discarded.
"""

import logging

import pywikibot

from .column import PropertyColumn, PropertySourceColumn, ReferenceColumn
from .error_category import ErrorCategory

logger = logging.getLogger("integraality.update")

# A single source expands to one column per property value, each driving its
# own SPARQL query. Cap the fan-out so one mis-configured dashboard can't
# generate hundreds of columns and hammer the query backend.
MAX_SOURCED_COLUMNS = 50


class ColumnSourceException(Exception):
    """The configured column source could not be resolved (bad/missing item).

    A config error: the dashboard points at an item that is deleted,
    missing, or a redirect."""

    error_category = ErrorCategory.CONFIG


class ColumnSourceResolver:
    """Expand PropertySourceColumn placeholders using a pywikibot repository."""

    def __init__(self, repo):
        """:param repo: a pywikibot DataSite (the Wikidata data repository)."""
        self.repo = repo

    def resolve_placeholders(self, columns):
        """Return a flat column list with every source placeholder expanded.

        Position-preserving (hybrid configs keep their order) and does not
        deduplicate.
        """
        resolved = []
        for column in columns:
            if isinstance(column, PropertySourceColumn):
                resolved.extend(self.resolve(column))
            else:
                resolved.append(column)
        return resolved

    def resolve(self, source_column):
        """Expand a single placeholder into ordered PropertyColumns."""
        item = pywikibot.ItemPage(self.repo, source_column.source_item)
        try:
            item_data = item.get()
        except pywikibot.exceptions.IsRedirectPageError as e:
            raise ColumnSourceException(
                f"Column source item {source_column.source_item} is a redirect; "
                "point the source at the target item instead."
            ) from e
        except pywikibot.exceptions.NoPageError as e:
            raise ColumnSourceException(
                f"Column source item {source_column.source_item} does not exist."
            ) from e
        claims = item_data.get("claims", {}).get(source_column.source_property, [])
        columns = []
        for claim in claims:
            property_id = self._property_id_from_claim(claim)
            if property_id is None:
                continue
            if source_column.reference_check is not None:
                columns.append(
                    ReferenceColumn(
                        property=property_id,
                        reference_check=source_column.reference_check,
                    )
                )
            else:
                columns.append(PropertyColumn(property=property_id))
        if len(columns) > MAX_SOURCED_COLUMNS:
            raise ColumnSourceException(
                f"Column source {source_column.get_key()} expands to "
                f"{len(columns)} columns, exceeding the limit of "
                f"{MAX_SOURCED_COLUMNS}."
            )
        if columns:
            logger.info(
                "Expanded column source %s into %d columns",
                source_column.get_key(),
                len(columns),
            )
        else:
            logger.warning(
                "Column source %s expanded to no columns; check that %s is set "
                "on %s and holds property values",
                source_column.get_key(),
                source_column.source_property,
                source_column.source_item,
            )
        return columns

    @staticmethod
    def _property_id_from_claim(claim):
        """Return the claim's target P-id, or None if it is not a property."""
        target = claim.getTarget()
        if isinstance(target, pywikibot.PropertyPage):
            return target.getID()
        return None
