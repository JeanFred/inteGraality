"""Tests for config_hash: the frozen canonical-serialization contract (T440134).

The golden-hash test is the real safeguard against accidental encoding drift.
If it fails after an intentional serialization change, re-pin it deliberately
(that is a reviewed re-hash of all configs).
"""

import unittest

from ..config_hash import (
    canonical_token_bag,
    compute_config_hash,
)

# A fixed config pinned to a known digest. Changing the serialization scheme
# changes this -- that is the intended, reviewed signal.
_GOLDEN_CONFIG = {
    "selector_sparql": "wdt:P31 wd:Q5",
    "grouping_property": "P21",
    "grouping_threshold": 20,
    "higher_grouping": None,
    "groupings": None,
    "row_totals": True,
    "row_no_group": False,
    "grouping_link_mode": "link",
    "column_keys": ["P569", "P570", "P1963(Q5)"],
}
_GOLDEN_HASH = "de32492f26ef1d2a7e0d778cd19f3f7708a72abc07b2da4b8544e4d60e7ec3d3"


class TestGoldenHash(unittest.TestCase):
    def test_known_config_hashes_to_known_digest(self):
        self.assertEqual(compute_config_hash(**_GOLDEN_CONFIG), _GOLDEN_HASH)


class TestCanonicalizationContract(unittest.TestCase):
    def _hash(self, **overrides):
        config = dict(_GOLDEN_CONFIG)
        config.update(overrides)
        return compute_config_hash(**config)

    def test_absent_threshold_equals_materialized_default(self):
        # The caller materializes the default (20); absent must never produce a
        # second hash for the same config.
        self.assertEqual(self._hash(grouping_threshold=20), _GOLDEN_HASH)

    def test_none_and_empty_higher_grouping_are_the_same_token(self):
        self.assertEqual(
            self._hash(higher_grouping=None),
            self._hash(higher_grouping=""),
        )

    def test_none_and_empty_groupings_are_the_same_token(self):
        self.assertEqual(
            self._hash(groupings=None),
            self._hash(groupings=""),
        )

    def test_column_order_is_significant(self):
        self.assertNotEqual(
            self._hash(column_keys=["P569", "P570", "P1963(Q5)"]),
            self._hash(column_keys=["P570", "P569", "P1963(Q5)"]),
        )

    def test_source_expression_is_hashed_not_expanded(self):
        # The authored source expression is one token; expanding it to its
        # children must change the hash (different authored config).
        self.assertNotEqual(
            self._hash(column_keys=["P569", "P570", "P1963(Q5)"]),
            self._hash(column_keys=["P569", "P570", "P18", "P856"]),
        )

    def test_threshold_change_changes_hash(self):
        self.assertNotEqual(self._hash(grouping_threshold=50), _GOLDEN_HASH)

    def test_boolean_flags_are_significant(self):
        self.assertNotEqual(self._hash(row_totals=False), _GOLDEN_HASH)
        self.assertNotEqual(self._hash(row_no_group=True), _GOLDEN_HASH)

    def test_grouping_property_none_differs_from_set(self):
        self.assertNotEqual(
            self._hash(grouping_property=None),
            self._hash(grouping_property="P21"),
        )


class TestCanonicalTokenBag(unittest.TestCase):
    def test_comma_padded_sorted_deduped(self):
        self.assertEqual(
            canonical_token_bag(["Q7889", "P31", "P31", "Q5"]),
            ",P31,Q5,Q7889,",
        )

    def test_empty_is_none(self):
        self.assertIsNone(canonical_token_bag([]))

    def test_whitespace_only_is_none(self):
        self.assertIsNone(canonical_token_bag(["", "   "]))

    def test_tokens_are_stripped(self):
        self.assertEqual(canonical_token_bag([" P31 ", "Q5"]), ",P31,Q5,")

    def test_single_token_still_padded_both_ends(self):
        # The pad is load-bearing: a lone token must match LIKE '%,P31,%'.
        self.assertEqual(canonical_token_bag(["P31"]), ",P31,")
