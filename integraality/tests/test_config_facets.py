"""Tests for config_facets: persistable facet extraction (T440134)."""

import unittest

from ..column import (
    AbstractColumn,
    DescriptionColumn,
    LabelColumn,
    PropertyColumn,
    QualifierColumn,
    ReferenceColumn,
    SitelinkColumn,
    TextColumn,
)
from ..config import ParsedConfig
from ..config_facets import (
    _column_facets,
    build_config_facets,
    explicit_groupings_bag,
    extract_column_facets,
    grouping_property_from_predicate,
    grouping_type_token,
    selector_mentions,
)
from ..grouping import (
    GroupingConfiguration,
    ItemGroupingType,
    SitelinkGroupingType,
    YearGroupingType,
)
from ..reference_check import GoodReferenceCheck


class TestGroupingPropertyFromPredicate(unittest.TestCase):
    def test_simple_wdt_predicate_yields_pid(self):
        self.assertEqual(grouping_property_from_predicate("wdt:P21"), "P21")

    def test_compound_path_is_none(self):
        self.assertIsNone(grouping_property_from_predicate("wdt:P131/wdt:P17"))

    def test_sitelink_predicate_is_none(self):
        self.assertIsNone(grouping_property_from_predicate("^schema:about"))

    def test_none_is_none(self):
        self.assertIsNone(grouping_property_from_predicate(None))


class TestGroupingTypeToken(unittest.TestCase):
    def test_item(self):
        self.assertEqual(grouping_type_token(ItemGroupingType()), "item")

    def test_year(self):
        self.assertEqual(grouping_type_token(YearGroupingType()), "year")

    def test_sitelink(self):
        self.assertEqual(grouping_type_token(SitelinkGroupingType()), "sitelink")

    def test_unresolved_is_none(self):
        self.assertIsNone(grouping_type_token(None))


class TestSelectorMentions(unittest.TestCase):
    def test_dedup_sorted_padded(self):
        self.assertEqual(
            selector_mentions("?x wdt:P31 wd:Q5 . ?x wdt:P31 wd:Q500"),
            ",P31,Q5,Q500,",
        )

    def test_no_ids_is_none(self):
        self.assertIsNone(selector_mentions("?x ?y ?z"))

    def test_tokenized_not_substring(self):
        # Q5 and Q500 are distinct tokens, never one matching the other.
        bag = selector_mentions("wd:Q500")
        self.assertEqual(bag, ",Q500,")


class TestExplicitGroupingsBag(unittest.TestCase):
    def test_raw_tokens_sorted_padded(self):
        self.assertEqual(
            explicit_groupings_bag("Q6581097,Q6581072"), ",Q6581072,Q6581097,"
        )

    def test_raw_codes_not_expanded(self):
        # Sitelink codes stay raw (enwiki), not expanded to URLs.
        self.assertEqual(explicit_groupings_bag("enwiki,frwiki"), ",enwiki,frwiki,")

    def test_none_is_none(self):
        self.assertIsNone(explicit_groupings_bag(None))

    def test_empty_is_none(self):
        self.assertIsNone(explicit_groupings_bag(""))


class TestExtractColumnFacets(unittest.TestCase):
    def test_maps_each_column_type(self):
        columns = [
            PropertyColumn(property="P569"),
            QualifierColumn(property="P1082", qualifier="P585"),
            ReferenceColumn(property="P18", reference_check=GoodReferenceCheck()),
            LabelColumn(language="en"),
            DescriptionColumn(language="fr"),
            SitelinkColumn(
                project="enwiki",
                project_data={"url": "https://en.wikipedia.org/", "item": "Q328"},
            ),
        ]
        facets = extract_column_facets(columns)
        self.assertEqual([f.position for f in facets], [0, 1, 2, 3, 4, 5])
        self.assertEqual(
            [f.column_type for f in facets],
            ["property", "qualifier", "reference", "label", "description", "sitelink"],
        )
        self.assertEqual(facets[0].property_id, "P569")
        self.assertEqual(facets[1].column_type, "qualifier")
        self.assertEqual(facets[2].reference_check_kind, "good")
        # good/any carry no atoms -> NULL token bag.
        self.assertIsNone(facets[2].reference_check_tokens)
        self.assertEqual(facets[3].language, "en")
        self.assertEqual(facets[4].language, "fr")
        self.assertEqual(facets[5].project, "enwiki")

    def test_reference_column_emits_kind_and_token_bag(self):
        from ..reference_check import (
            AnyOfPropertiesReferenceCheck,
            PropertyReferenceCheck,
        )

        valued = extract_column_facets(
            [
                ReferenceColumn(
                    property="P50",
                    reference_check=PropertyReferenceCheck("P248", "Q19216625"),
                )
            ]
        )[0]
        self.assertEqual(valued.reference_check_kind, "property")
        self.assertEqual(valued.reference_check_tokens, ",S248=Q19216625,")

        multi = extract_column_facets(
            [
                ReferenceColumn(
                    property="P50",
                    reference_check=AnyOfPropertiesReferenceCheck(
                        [("P248", None), ("P854", None)]
                    ),
                )
            ]
        )[0]
        self.assertEqual(multi.reference_check_kind, "any_of")
        self.assertEqual(multi.reference_check_tokens, ",S248,S854,")

    def test_source_provenance_preserved(self):
        columns = [
            PropertyColumn(property="P18", source_property="P1963", source_item="Q5"),
        ]
        facet = extract_column_facets(columns)[0]
        self.assertEqual(facet.source_property, "P1963")
        self.assertEqual(facet.source_item, "Q5")
        self.assertEqual(facet.raw_key, "P18")

    def test_directly_authored_has_no_source(self):
        facet = extract_column_facets([PropertyColumn(property="P18")])[0]
        self.assertIsNone(facet.source_property)
        self.assertIsNone(facet.source_item)

    def test_qualifier_column_emits_qualifier_and_value(self):
        facet = extract_column_facets(
            [QualifierColumn(property="P39", qualifier="P580", value="Q30")]
        )[0]
        self.assertEqual(facet.qualifier_id, "P580")
        self.assertEqual(facet.value, "Q30")
        self.assertEqual(facet.value_item, "Q30")
        self.assertIsNone(facet.value_traversal)

    def test_qualifierless_column_has_no_value_facets(self):
        facet = extract_column_facets(
            [QualifierColumn(property="P1082", qualifier="P585")]
        )[0]
        self.assertEqual(facet.qualifier_id, "P585")
        self.assertIsNone(facet.value)
        self.assertIsNone(facet.value_item)

    def test_plain_property_column_has_no_value_facets(self):
        facet = extract_column_facets([PropertyColumn(property="P569")])[0]
        self.assertIsNone(facet.value)
        self.assertIsNone(facet.value_item)
        self.assertIsNone(facet.qualifier_id)

    def test_value_traversal_split_into_item_and_suffix(self):
        facet = extract_column_facets(
            [QualifierColumn(property="P1435", qualifier="P580", value="Q358~P279*")]
        )[0]
        # The bare Q-id is facetable; the path suffix is kept verbatim.
        self.assertEqual(facet.value_item, "Q358")
        self.assertEqual(facet.value_traversal, "P279*")
        self.assertEqual(facet.value, "Q358~P279*")

    def test_reference_column_also_emits_value_and_qualifier(self):
        # A reference column scoped to a value+qualifier lights up BOTH the
        # reference facets and the value/qualifier facets (no conflict).
        facet = extract_column_facets(
            [
                ReferenceColumn(
                    property="P143",
                    value="Q328",
                    qualifier="P580",
                    reference_check=GoodReferenceCheck(),
                )
            ]
        )[0]
        self.assertEqual(facet.reference_check_kind, "good")
        self.assertEqual(facet.qualifier_id, "P580")
        self.assertEqual(facet.value_item, "Q328")


class TestBuildConfigFacets(unittest.TestCase):
    def _config(self, **overrides):
        gc = overrides.pop(
            "grouping_configuration",
            GroupingConfiguration(
                predicate="wdt:P21",
                grouping_threshold=20,
                grouping_type=ItemGroupingType(),
            ),
        )
        fields = {
            "selector_sparql": "wdt:P31 wd:Q5",
            "grouping_configuration": gc,
            "sparql_query_engine": object(),
            "row_totals": True,
            "row_no_group": False,
            "grouping_link_mode": "link",
            "raw_grouping_property": "P21",
            "raw_groupings": None,
            "authored_column_keys": ("P569", "P1963(Q5)"),
            "columns": (
                PropertyColumn(property="P569"),
                PropertyColumn(
                    property="P18", source_property="P1963", source_item="Q5"
                ),
            ),
        }
        fields.update(overrides)
        return ParsedConfig(**fields)

    def _facets(self, **overrides):
        return build_config_facets(self._config(**overrides))

    def test_assembles_facets(self):
        facets = self._facets()
        self.assertEqual(facets.grouping_predicate, "wdt:P21")
        self.assertEqual(facets.grouping_property, "P21")
        self.assertEqual(facets.grouping_type, "item")
        self.assertEqual(facets.grouping_threshold, 20)
        self.assertEqual(facets.selector_mentions, ",P31,Q5,")
        self.assertEqual(len(facets.columns), 2)
        self.assertEqual(len(facets.config_hash), 64)

    def test_hash_uses_authored_keys_not_expanded(self):
        # Different expanded columns, same authored keys -> same hash.
        a = self._facets(columns=(PropertyColumn(property="P569"),))
        b = self._facets(
            columns=(
                PropertyColumn(property="P569"),
                PropertyColumn(property="P18"),
                PropertyColumn(property="P856"),
            )
        )
        self.assertEqual(a.config_hash, b.config_hash)

    def test_compound_predicate_has_null_grouping_property(self):
        gc = GroupingConfiguration(
            predicate="wdt:P131/wdt:P17",
            grouping_threshold=20,
            grouping_type=ItemGroupingType(),
        )
        facets = self._facets(grouping_configuration=gc)
        self.assertIsNone(facets.grouping_property)
        self.assertEqual(facets.grouping_predicate, "wdt:P131/wdt:P17")

    def test_against_a_real_assembled_config(self):
        # Guard against ParsedConfig shape drift: drive build_config_facets
        # through a genuine ConfigAssembler.parse_config output, not a
        # hand-built config. A mismatch between what parse_config populates and
        # what build_config_facets reads would surface here.
        from ..config_assembler import ConfigAssembler

        config = ConfigAssembler(
            site_url="https://www.wikidata.org/wiki/"
        ).parse_config(
            {
                "grouping_property": "P21",
                "groupings": "Q6581072,Q6581097",
                "columns": "P569,P1963(Q5)",
                "selector_sparql": "wdt:P31 wd:Q5",
            }
        )
        facets = build_config_facets(config)
        self.assertEqual(facets.grouping_property, "P21")
        self.assertEqual(facets.grouping_predicate, "wdt:P21")
        self.assertEqual(facets.explicit_groupings, ",Q6581072,Q6581097,")
        self.assertEqual(facets.selector_mentions, ",P31,Q5,")
        self.assertEqual(len(facets.config_hash), 64)


class TestEveryColumnTypeMapsToFacets(unittest.TestCase):
    """A new concrete column type must be wired into _column_facets, not fall
    through to the ValueError. Mirrors the ReferenceCheck.kind leaf guard."""

    # Abstract bases in the AbstractColumn tree that are never a column type on
    # their own (TextColumn is the Label/Description base; AbstractColumn the root).
    _ABSTRACT_BASES = (AbstractColumn, TextColumn)

    @staticmethod
    def _concrete_column_classes():
        def walk(base):
            found = []
            for sub in base.__subclasses__():
                found.extend(walk(sub))
                found.append(sub)
            return found

        classes = set(walk(AbstractColumn))
        return [
            c
            for c in classes
            if c not in TestEveryColumnTypeMapsToFacets._ABSTRACT_BASES
        ]

    @staticmethod
    def _instance(column_cls):
        """A minimal valid instance per concrete column type."""
        if issubclass(column_cls, ReferenceColumn):
            return column_cls(property="P18", reference_check=GoodReferenceCheck())
        if issubclass(column_cls, QualifierColumn):
            return column_cls(property="P1082", qualifier="P585")
        if issubclass(column_cls, PropertyColumn):
            return column_cls(property="P569")
        if issubclass(column_cls, (LabelColumn, DescriptionColumn)):
            return column_cls(language="en")
        if issubclass(column_cls, SitelinkColumn):
            return column_cls(
                project="enwiki",
                project_data={"url": "https://en.wikipedia.org/", "item": "Q328"},
            )
        raise AssertionError(
            f"No representative instance wired for {column_cls.__name__}"
        )

    def test_every_concrete_column_type_maps_to_facets(self):
        classes = self._concrete_column_classes()
        self.assertTrue(classes)  # sanity: discovery found the leaves
        for cls in classes:
            instance = self._instance(cls)
            facet = _column_facets(0, instance)
            # column_type is the column's own self-description, and the facet
            # extractor must have a branch for it (no ValueError fallthrough).
            self.assertEqual(
                facet.column_type,
                instance.get_type_name(),
                f"{cls.__name__} maps to the wrong column_type",
            )
