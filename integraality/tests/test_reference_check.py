# -*- coding: utf-8  -*-

import unittest

from ..reference_check import (
    AllPropertiesReferenceCheck,
    AnyOfPropertiesReferenceCheck,
    AnyReferenceCheck,
    GoodReferenceCheck,
    PropertyReferenceCheck,
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
