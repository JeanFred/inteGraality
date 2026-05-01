# -*- coding: utf-8  -*-

import unittest

from ..grouping_link import (
    GroupingLinkMaker,
    GroupingLinkSyntaxException,
    IdGroupingLink,
    LabelGroupingLink,
    NoGroupingLink,
)


class TestGroupingLinkMaker(unittest.TestCase):
    def test_none_returns_no_grouping_link(self):
        result = GroupingLinkMaker.make(None)
        self.assertIsInstance(result, NoGroupingLink)

    def test_bare_string_returns_label_en_compat(self):
        result = GroupingLinkMaker.make("Foo")
        expected = LabelGroupingLink(template="Foo/{Len}")
        self.assertEqual(result, expected)

    def test_explicit_label_french(self):
        result = GroupingLinkMaker.make("Foo/{Lfr}")
        expected = LabelGroupingLink(template="Foo/{Lfr}", lang="fr")
        self.assertEqual(result, expected)

    def test_explicit_label_mul(self):
        result = GroupingLinkMaker.make("Bar/{Lmul}")
        expected = LabelGroupingLink(template="Bar/{Lmul}", lang="mul")
        self.assertEqual(result, expected)

    def test_explicit_label_zh_hans(self):
        result = GroupingLinkMaker.make("Foo/{Lzh-hans}")
        expected = LabelGroupingLink(template="Foo/{Lzh-hans}", lang="zh-hans")
        self.assertEqual(result, expected)

    def test_unsupported_placeholder(self):
        with self.assertRaises(GroupingLinkSyntaxException):
            GroupingLinkMaker.make("Foo/{foo}")

    def test_multiple_placeholders(self):
        with self.assertRaises(GroupingLinkSyntaxException):
            GroupingLinkMaker.make("Foo/{Len}/{Lfr}")

    def test_id_placeholder(self):
        result = GroupingLinkMaker.make("Foo/{id}")
        expected = IdGroupingLink(template="Foo/{id}")
        self.assertEqual(result, expected)


class TestNoGroupingLink(unittest.TestCase):
    def test_resolve_returns_none(self):
        link = NoGroupingLink()
        self.assertIsNone(link.resolve("Q123", {}))

    def test_get_select_clause(self):
        self.assertEqual(NoGroupingLink().get_select_clause(), "")

    def test_get_sparql_fragment(self):
        self.assertEqual(NoGroupingLink().get_sparql_fragment(), ([], None))


class TestLabelGroupingLink(unittest.TestCase):
    def setUp(self):
        self.link = LabelGroupingLink(template="Foo/{Len}")

    def test_resolve_with_label_value(self):
        result = self.link.resolve("Q123", {"grouping_link_value": "Bar"})
        self.assertEqual(result, "Foo/Bar")

    def test_resolve_falls_back_to_qid(self):
        result = self.link.resolve("Q123", {})
        self.assertEqual(result, "Foo/Q123")

    def test_resolve_falls_back_to_qid_on_empty_value(self):
        result = self.link.resolve("Q123", {"grouping_link_value": ""})
        self.assertEqual(result, "Foo/Q123")

    def test_get_select_clause(self):
        self.assertEqual(self.link.get_select_clause(), "?grouping_link_value")

    def test_get_sparql_fragment(self):
        (fragment, group_by) = self.link.get_sparql_fragment()
        self.assertEqual(group_by, "?grouping_link_value")
        self.assertEqual(
            fragment,
            [
                "  OPTIONAL {{",
                "    ?grouping rdfs:label ?groupinglabelMUL.",
                "    FILTER(lang(?groupinglabelMUL)='mul')",
                "  }}.",
                "  OPTIONAL {{",
                "    ?grouping rdfs:label ?groupinglabelEN.",
                "    FILTER(lang(?groupinglabelEN)='en')",
                "  }}.",
                "  BIND(COALESCE(?groupinglabelEN, ?groupinglabelMUL) AS ?grouping_link_value).",
            ],
        )


class TestLabelGroupingLinkFrench(unittest.TestCase):
    def setUp(self):
        self.link = LabelGroupingLink(template="Foo/{Lfr}", lang="fr")

    def test_resolve(self):
        result = self.link.resolve("Q456", {"grouping_link_value": "Chose"})
        self.assertEqual(result, "Foo/Chose")

    def test_get_sparql_fragment(self):
        (fragment, group_by) = self.link.get_sparql_fragment()
        self.assertEqual(group_by, "?grouping_link_value")
        self.assertEqual(
            fragment,
            [
                "  OPTIONAL {{",
                "    ?grouping rdfs:label ?groupinglabelMUL.",
                "    FILTER(lang(?groupinglabelMUL)='mul')",
                "  }}.",
                "  OPTIONAL {{",
                "    ?grouping rdfs:label ?groupinglabelFR.",
                "    FILTER(lang(?groupinglabelFR)='fr')",
                "  }}.",
                "  BIND(COALESCE(?groupinglabelFR, ?groupinglabelMUL) AS ?grouping_link_value).",
            ],
        )


class TestIdGroupingLink(unittest.TestCase):
    def setUp(self):
        self.link = IdGroupingLink(template="Foo/{id}")

    def test_resolve(self):
        result = self.link.resolve("Q123", {})
        self.assertEqual(result, "Foo/Q123")

    def test_resolve_ignores_label(self):
        result = self.link.resolve("Q123", {"grouping_link_value": "Bar"})
        self.assertEqual(result, "Foo/Q123")

    def test_get_select_clause(self):
        self.assertEqual(self.link.get_select_clause(), "")

    def test_get_sparql_fragment(self):
        self.assertEqual(self.link.get_sparql_fragment(), ([], None))
