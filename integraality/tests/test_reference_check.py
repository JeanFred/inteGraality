import unittest

from ..reference_check import (
    AllPropertiesReferenceCheck,
    AnyOfPropertiesReferenceCheck,
    AnyReferenceCheck,
    GoodReferenceCheck,
    MultiPropertyReferenceCheck,
    PropertyReferenceCheck,
    ReferenceCheck,
)


class TestReferenceCheckStrategies(unittest.TestCase):
    def test_any_reference_check_pattern(self):
        check = AnyReferenceCheck()
        result = check.sparql_pattern()
        self.assertEqual(result, "?_unreferenced_stmt prov:wasDerivedFrom []")

    def test_any_reference_check_key_suffix(self):
        self.assertEqual(AnyReferenceCheck().key_suffix(), "S*")

    def test_any_reference_check_column_label_suffix(self):
        self.assertEqual(AnyReferenceCheck().column_label_suffix(), "📚")

    def test_any_reference_check_format_html_label(self):
        result = AnyReferenceCheck().format_html_label("<a>P131</a>")
        self.assertEqual(result, "<a>P131</a> referenced")

    def test_any_reference_check_equality(self):
        self.assertEqual(AnyReferenceCheck(), AnyReferenceCheck())

    def test_property_reference_check_pattern(self):
        check = PropertyReferenceCheck("P248")
        result = check.sparql_pattern()
        self.assertEqual(result, "?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 []")

    def test_property_reference_check_key_suffix(self):
        self.assertEqual(PropertyReferenceCheck("P248").key_suffix(), "S248")

    def test_property_reference_check_column_label_suffix(self):
        self.assertEqual(
            PropertyReferenceCheck("P248").column_label_suffix(),
            "📚{{Property|P248}}",
        )

    def test_property_reference_check_format_html_label(self):
        result = PropertyReferenceCheck("P248").format_html_label("<a>P131</a>")
        expected = (
            "<a>P131</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
        )
        self.assertEqual(result, expected)

    def test_property_reference_check_equality(self):
        self.assertEqual(PropertyReferenceCheck("P248"), PropertyReferenceCheck("P248"))
        self.assertNotEqual(
            PropertyReferenceCheck("P248"), PropertyReferenceCheck("P854")
        )

    def test_any_of_properties_reference_check_pattern(self):
        check = AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)])
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "{ ?_ref pr:P248 [] } UNION { ?_ref pr:P854 [] }"
        )
        self.assertEqual(result, expected)

    def test_any_of_properties_reference_check_key_suffix(self):
        self.assertEqual(
            AnyOfPropertiesReferenceCheck(
                [("P248", None), ("P854", None)]
            ).key_suffix(),
            "S248;S854",
        )

    def test_any_of_properties_reference_check_column_label_suffix(self):
        self.assertEqual(
            AnyOfPropertiesReferenceCheck(
                [("P248", None), ("P854", None)]
            ).column_label_suffix(),
            "📚{{Property|P248}}/{{Property|P854}}",
        )

    def test_any_of_properties_reference_check_format_html_label(self):
        result = AnyOfPropertiesReferenceCheck(
            [("P248", None), ("P854", None)]
        ).format_html_label("<a>P131</a>")
        expected = (
            "<a>P131</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
            " / "
            '<a href="https://wikidata.org/wiki/Property:P854">P854</a>'
        )
        self.assertEqual(result, expected)

    def test_any_of_properties_reference_check_equality(self):
        self.assertEqual(
            AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)]),
            AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)]),
        )
        self.assertNotEqual(
            AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)]),
            AnyOfPropertiesReferenceCheck([("P248", None)]),
        )

    def test_any_of_properties_reference_check_with_value_pattern(self):
        check = AnyOfPropertiesReferenceCheck([("P248", "Q135436770"), ("P854", None)])
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "{ ?_ref pr:P248 wd:Q135436770 } UNION { ?_ref pr:P854 [] }"
        )
        self.assertEqual(result, expected)

    def test_all_properties_reference_check_pattern(self):
        check = AllPropertiesReferenceCheck([("P248", None), ("P304", None)])
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "?_ref pr:P248 [] .\n"
            "?_ref pr:P304 [] ."
        )
        self.assertEqual(result, expected)

    def test_all_properties_reference_check_key_suffix(self):
        self.assertEqual(
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]).key_suffix(),
            "S248+S304",
        )

    def test_all_properties_reference_check_column_label_suffix(self):
        self.assertEqual(
            AllPropertiesReferenceCheck(
                [("P248", None), ("P304", None)]
            ).column_label_suffix(),
            "📚{{Property|P248}}+{{Property|P304}}",
        )

    def test_all_properties_reference_check_format_html_label(self):
        result = AllPropertiesReferenceCheck(
            [("P248", None), ("P304", None)]
        ).format_html_label("<a>P131</a>")
        expected = (
            "<a>P131</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
            " + "
            '<a href="https://wikidata.org/wiki/Property:P304">P304</a>'
        )
        self.assertEqual(result, expected)

    def test_all_properties_reference_check_equality(self):
        self.assertEqual(
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]),
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]),
        )
        self.assertNotEqual(
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]),
            AllPropertiesReferenceCheck([("P248", None)]),
        )

    def test_all_properties_reference_check_with_value_pattern(self):
        check = AllPropertiesReferenceCheck([("P248", "Q135436770"), ("P813", None)])
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "?_ref pr:P248 wd:Q135436770 .\n"
            "?_ref pr:P813 [] ."
        )
        self.assertEqual(result, expected)

    def test_all_properties_reference_check_with_value_key_suffix(self):
        self.assertEqual(
            AllPropertiesReferenceCheck(
                [("P248", "Q135436770"), ("P813", None)]
            ).key_suffix(),
            "S248=Q135436770+S813",
        )

    def test_all_properties_reference_check_with_value_column_label(self):
        self.assertEqual(
            AllPropertiesReferenceCheck(
                [("P248", "Q135436770"), ("P813", None)]
            ).column_label_suffix(),
            "📚{{Property|P248}}={{Q|Q135436770}}+{{Property|P813}}",
        )

    def test_all_properties_reference_check_with_value_html_label(self):
        result = AllPropertiesReferenceCheck(
            [("P248", "Q135436770"), ("P813", None)]
        ).format_html_label("<a>P136</a>")
        expected = (
            "<a>P136</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
            '=<a href="https://wikidata.org/wiki/Q135436770">Q135436770</a>'
            " + "
            '<a href="https://wikidata.org/wiki/Property:P813">P813</a>'
        )
        self.assertEqual(result, expected)

    def test_property_value_reference_check_pattern(self):
        check = PropertyReferenceCheck("P248", "Q19216625")
        result = check.sparql_pattern()
        expected = "?_unreferenced_stmt prov:wasDerivedFrom/pr:P248 wd:Q19216625"
        self.assertEqual(result, expected)

    def test_property_value_reference_check_key_suffix(self):
        self.assertEqual(
            PropertyReferenceCheck("P248", "Q19216625").key_suffix(), "S248=Q19216625"
        )

    def test_property_value_reference_check_column_label_suffix(self):
        self.assertEqual(
            PropertyReferenceCheck("P248", "Q19216625").column_label_suffix(),
            "📚{{Property|P248}}={{Q|Q19216625}}",
        )

    def test_property_value_reference_check_format_html_label(self):
        result = PropertyReferenceCheck("P248", "Q19216625").format_html_label(
            "<a>P131</a>"
        )
        expected = (
            "<a>P131</a> referenced with "
            '<a href="https://wikidata.org/wiki/Property:P248">P248</a>'
            "="
            '<a href="https://wikidata.org/wiki/Q19216625">Q19216625</a>'
        )
        self.assertEqual(result, expected)

    def test_property_value_reference_check_equality(self):
        self.assertEqual(
            PropertyReferenceCheck("P248", "Q19216625"),
            PropertyReferenceCheck("P248", "Q19216625"),
        )
        self.assertNotEqual(
            PropertyReferenceCheck("P248", "Q19216625"),
            PropertyReferenceCheck("P248", "Q99999"),
        )
        self.assertNotEqual(
            PropertyReferenceCheck("P248", "Q19216625"),
            PropertyReferenceCheck("P854", "Q19216625"),
        )
        self.assertNotEqual(
            PropertyReferenceCheck("P248", "Q19216625"),
            PropertyReferenceCheck("P248"),
        )

    def test_different_checks_not_equal(self):
        self.assertNotEqual(AnyReferenceCheck(), PropertyReferenceCheck("P248"))
        self.assertNotEqual(AnyReferenceCheck(), GoodReferenceCheck())
        self.assertNotEqual(PropertyReferenceCheck("P248"), GoodReferenceCheck())
        self.assertNotEqual(
            PropertyReferenceCheck("P248"),
            AnyOfPropertiesReferenceCheck([("P248", None)]),
        )
        self.assertNotEqual(
            AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)]),
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]),
        )
        self.assertNotEqual(
            PropertyReferenceCheck("P248"),
            PropertyReferenceCheck("P248", "Q19216625"),
        )

    def test_good_reference_check_pattern(self):
        check = GoodReferenceCheck()
        result = check.sparql_pattern()
        expected = (
            "?_unreferenced_stmt prov:wasDerivedFrom ?_ref .\n"
            "FILTER NOT EXISTS { ?_ref pr:P143 [] }\n"
            "FILTER NOT EXISTS { ?_ref pr:P3452 [] }\n"
            "FILTER NOT EXISTS { ?_ref pr:P887 [] }"
        )
        self.assertEqual(result, expected)

    def test_good_reference_check_key_suffix(self):
        self.assertEqual(GoodReferenceCheck().key_suffix(), "S!")

    def test_good_reference_check_column_label_suffix(self):
        self.assertEqual(GoodReferenceCheck().column_label_suffix(), "📚✓")

    def test_good_reference_check_format_html_label(self):
        result = GoodReferenceCheck().format_html_label("<a>P131</a>")
        self.assertEqual(result, "<a>P131</a> well-referenced")

    def test_good_reference_check_equality(self):
        self.assertEqual(GoodReferenceCheck(), GoodReferenceCheck())

    def test_kind_tokens(self):
        self.assertEqual(AnyReferenceCheck().kind, "any")
        self.assertEqual(GoodReferenceCheck().kind, "good")
        self.assertEqual(PropertyReferenceCheck("P248").kind, "property")
        self.assertEqual(PropertyReferenceCheck("P248", "Q19216625").kind, "property")
        self.assertEqual(
            AnyOfPropertiesReferenceCheck([("P248", None), ("P854", None)]).kind,
            "any_of",
        )
        self.assertEqual(
            AllPropertiesReferenceCheck([("P248", None), ("P304", None)]).kind,
            "all_of",
        )

    def test_every_concrete_leaf_defines_kind(self):
        # The runtime guard that replaces @abstractmethod for `kind`.
        valid = {"any", "good", "property", "any_of", "all_of"}
        leaves = self._concrete_leaves(ReferenceCheck)
        self.assertTrue(leaves)  # sanity: we actually found subclasses
        for leaf in leaves:
            kind = getattr(leaf, "kind", None)
            self.assertIsInstance(
                kind, str, f"{leaf.__name__} is missing a `kind` token"
            )
            self.assertTrue(kind, f"{leaf.__name__} has an empty `kind`")
            self.assertIn(kind, valid, f"{leaf.__name__} has unknown kind")

    @staticmethod
    def _concrete_leaves(base):
        """All instantiable (non-abstract) subclasses of base, recursively."""
        leaves = []
        for sub in base.__subclasses__():
            leaves.extend(TestReferenceCheckStrategies._concrete_leaves(sub))
            if not getattr(sub, "__abstractmethods__", None):
                leaves.append(sub)
        return leaves

    def test_reference_atoms_empty_for_any_and_good(self):
        self.assertEqual(AnyReferenceCheck().reference_atoms(), [])
        self.assertEqual(GoodReferenceCheck().reference_atoms(), [])

    def test_reference_atoms_single_for_property(self):
        self.assertEqual(PropertyReferenceCheck("P248").reference_atoms(), ["S248"])

    def test_reference_atoms_valued_is_atoms_only(self):
        self.assertEqual(
            PropertyReferenceCheck("P248", "Q19216625").reference_atoms(),
            ["S248=Q19216625"],
        )

    def test_reference_atoms_multi_returns_each_part(self):
        self.assertEqual(
            AnyOfPropertiesReferenceCheck(
                [("P248", None), ("P854", None)]
            ).reference_atoms(),
            ["S248", "S854"],
        )
        self.assertEqual(
            AllPropertiesReferenceCheck(
                [("P248", "Q135436770"), ("P813", None)]
            ).reference_atoms(),
            ["S248=Q135436770", "S813"],
        )

    def test_every_concrete_leaf_reference_atoms_is_list(self):
        # Parallel safeguard to the kind guard: a new leaf must return a list
        # (empty only for the valueless any/good).
        valueless = (AnyReferenceCheck, GoodReferenceCheck)
        for leaf in self._concrete_leaves(ReferenceCheck):
            atoms = self._make_instance(leaf).reference_atoms()
            self.assertIsInstance(atoms, list, f"{leaf.__name__} atoms not a list")
            if leaf in valueless:
                self.assertEqual(atoms, [], f"{leaf.__name__} should have no atoms")
            else:
                self.assertTrue(atoms, f"{leaf.__name__} should expose atoms")

    @staticmethod
    def _make_instance(leaf):
        """A representative instance of a concrete leaf, for the atoms safeguard.

        Covers the two constructor shapes (valueless / property / list-of-pairs)
        from the leaf's own signature, so a newly-added leaf is handled or fails
        loudly here rather than being silently skipped by a stale lookup table.
        """
        if issubclass(leaf, MultiPropertyReferenceCheck):
            return leaf([("P248", None)])
        if issubclass(leaf, PropertyReferenceCheck):
            return leaf("P248")
        return leaf()
