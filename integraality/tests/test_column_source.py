"""Unit tests for column_source.py."""

import unittest
from unittest.mock import MagicMock, patch

from ..column import LabelColumn, PropertyColumn, PropertySourceColumn
from ..column_source import (
    MAX_SOURCED_COLUMNS,
    ColumnSourceException,
    ColumnSourceResolver,
)


class ColumnSourceResolverTest(unittest.TestCase):
    def setUp(self):
        self.repo = MagicMock()
        self.resolver = ColumnSourceResolver(repo=self.repo)
        # Patch pywikibot used inside column_source: ItemPage + the
        # PropertyPage isinstance check.
        patcher = patch("integraality.column_source.pywikibot")
        self.pywikibot = patcher.start()
        self.addCleanup(patcher.stop)
        # Make isinstance(target, pywikibot.PropertyPage) work: property-claim
        # targets are instances of a sentinel class, others are not.
        self.pywikibot.PropertyPage = _PropertyPageSentinel
        # Real exception classes so resolve() can raise/except them (the
        # patched module would otherwise expose MagicMocks here).
        self.pywikibot.exceptions.NoPageError = _NoPageError
        self.pywikibot.exceptions.IsRedirectPageError = _IsRedirectPageError

    def _item_with_claims(self, property_id, claims):
        """Wire pywikibot.ItemPage(...).get() to return the given claims."""
        item = MagicMock()
        item.get.return_value = {"claims": {property_id: claims}}
        self.pywikibot.ItemPage.return_value = item
        return item

    def _prop_claim(self, property_id):
        """A claim whose target is a PropertyPage sentinel with that id."""
        target = _PropertyPageSentinel(property_id)
        claim = MagicMock()
        claim.getTarget.return_value = target
        return claim

    def _other_claim(self):
        """A claim whose target is not a PropertyPage."""
        claim = MagicMock()
        claim.getTarget.return_value = object()
        return claim

    def test_resolve_in_order(self):
        claims = [
            self._prop_claim("P31"),
            self._prop_claim("P625"),
            self._prop_claim("P18"),
        ]
        self._item_with_claims("P1963", claims)
        source = PropertySourceColumn(source_property="P1963", source_item="Q39715")
        result = self.resolver.resolve(source)
        self.assertEqual(
            result,
            [
                PropertyColumn(property="P31"),
                PropertyColumn(property="P625"),
                PropertyColumn(property="P18"),
            ],
        )

    def test_resolve_discards_non_property_values(self):
        claims = [
            self._prop_claim("P31"),
            self._other_claim(),
            self._prop_claim("P18"),
        ]
        self._item_with_claims("P1963", claims)
        source = PropertySourceColumn(source_property="P1963", source_item="Q39715")
        result = self.resolver.resolve(source)
        self.assertEqual(
            result,
            [PropertyColumn(property="P31"), PropertyColumn(property="P18")],
        )

    def test_resolve_no_claims(self):
        item = MagicMock()
        item.get.return_value = {"claims": {}}
        self.pywikibot.ItemPage.return_value = item
        source = PropertySourceColumn(source_property="P1963", source_item="Q39715")
        self.assertEqual(self.resolver.resolve(source), [])

    def test_resolve_placeholders_hybrid_preserves_position(self):
        claims = [self._prop_claim("P31"), self._prop_claim("P18")]
        self._item_with_claims("P1963", claims)
        columns = [
            PropertyColumn(property="P136"),
            PropertySourceColumn(source_property="P1963", source_item="Q39715"),
            LabelColumn(language="en"),
        ]
        result = self.resolver.resolve_placeholders(columns)
        self.assertEqual(
            result,
            [
                PropertyColumn(property="P136"),
                PropertyColumn(property="P31"),
                PropertyColumn(property="P18"),
                LabelColumn(language="en"),
            ],
        )

    def test_resolve_placeholders_no_dedup(self):
        claims = [self._prop_claim("P136"), self._prop_claim("P18")]
        self._item_with_claims("P1963", claims)
        columns = [
            PropertyColumn(property="P136"),
            PropertySourceColumn(source_property="P1963", source_item="Q39715"),
        ]
        result = self.resolver.resolve_placeholders(columns)
        self.assertEqual(
            result,
            [
                PropertyColumn(property="P136"),
                PropertyColumn(property="P136"),
                PropertyColumn(property="P18"),
            ],
        )

    def test_resolve_placeholders_without_source_is_passthrough(self):
        columns = [PropertyColumn(property="P136"), LabelColumn(language="en")]
        result = self.resolver.resolve_placeholders(columns)
        self.assertEqual(result, columns)

    def _item_raising(self, exc):
        item = MagicMock()
        item.get.side_effect = exc
        self.pywikibot.ItemPage.return_value = item

    def test_resolve_missing_item_raises_config_error(self):
        self._item_raising(_NoPageError())
        source = PropertySourceColumn(source_property="P1963", source_item="Q404")
        with self.assertRaises(ColumnSourceException):
            self.resolver.resolve(source)

    def test_resolve_redirect_item_raises_config_error(self):
        self._item_raising(_IsRedirectPageError())
        source = PropertySourceColumn(source_property="P1963", source_item="Q39715")
        with self.assertRaises(ColumnSourceException):
            self.resolver.resolve(source)

    def test_resolve_exceeding_cap_raises(self):
        claims = [self._prop_claim(f"P{i}") for i in range(MAX_SOURCED_COLUMNS + 1)]
        self._item_with_claims("P1963", claims)
        source = PropertySourceColumn(source_property="P1963", source_item="Q39715")
        with self.assertRaises(ColumnSourceException):
            self.resolver.resolve(source)

    def test_resolve_at_cap_is_allowed(self):
        claims = [self._prop_claim(f"P{i}") for i in range(MAX_SOURCED_COLUMNS)]
        self._item_with_claims("P1963", claims)
        source = PropertySourceColumn(source_property="P1963", source_item="Q39715")
        self.assertEqual(len(self.resolver.resolve(source)), MAX_SOURCED_COLUMNS)

    def test_resolve_logs_expansion(self):
        self._item_with_claims(
            "P1963", [self._prop_claim("P31"), self._prop_claim("P18")]
        )
        source = PropertySourceColumn(source_property="P1963", source_item="Q39715")
        with self.assertLogs("integraality.update", level="INFO") as cm:
            self.resolver.resolve(source)
        self.assertTrue(
            any(
                "Expanded column source P1963(Q39715) into 2 columns" in m
                for m in cm.output
            )
        )

    def test_resolve_empty_logs_warning(self):
        # A source that yields nothing (wrong property/item) warns the editor.
        self._item_with_claims("P1963", [self._other_claim()])
        source = PropertySourceColumn(source_property="P1963", source_item="Q39715")
        with self.assertLogs("integraality.update", level="WARNING") as cm:
            result = self.resolver.resolve(source)
        self.assertEqual(result, [])
        self.assertTrue(any("expanded to no columns" in m for m in cm.output))


class _NoPageError(Exception):
    pass


class _IsRedirectPageError(Exception):
    pass


class _PropertyPageSentinel:
    """Stand-in for pywikibot.PropertyPage in tests.

    Used both as the type for isinstance checks and to build property-claim
    targets with a getID().
    """

    def __init__(self, property_id=None):
        self.property_id = property_id

    def getID(self):
        return self.property_id
