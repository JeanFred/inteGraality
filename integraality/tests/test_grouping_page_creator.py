# -*- coding: utf-8  -*-

import collections
import unittest
from unittest.mock import MagicMock, patch

import pywikibot

from ..column import PropertyColumn
from ..grouping_page_creator import GroupingPageCreator
from ..line import ItemGrouping, NoGroupGrouping, TotalsGrouping


@patch("integraality.grouping_page_creator.save_to_wiki_or_local")
@patch("integraality.grouping_page_creator.pywikibot.Page")
class GroupingPageCreatorTest(unittest.TestCase):
    def setUp(self):
        self.site = MagicMock()
        self.columns = collections.OrderedDict(
            [("P136", PropertyColumn("P136")), ("P178", PropertyColumn("P178"))]
        )
        self.creator = GroupingPageCreator(
            site=self.site,
            selector_sparql="wdt:P31/wdt:P279* wd:Q7889",
            grouping_predicate="wdt:P400",
            columns=self.columns,
            page_title="Wikidata:WikiProject Video games/Statistics/Platform",
        )

    def _make_local_page(self, mock_page_cls, exists=False):
        mock_page = MagicMock()
        mock_page.exists.return_value = exists
        mock_page.site = self.site
        mock_page_cls.return_value = mock_page
        return mock_page

    def test_creates_missing_page(self, mock_page_cls, mock_save):
        self._make_local_page(mock_page_cls, exists=False)
        grouping = ItemGrouping(
            count=10, title="Q751719", grouping_link="Foo/Game Gear"
        )
        self.creator.create_pages([grouping])

        mock_page_cls.assert_called_once_with(self.site, "Foo/Game Gear")
        mock_save.assert_called_once()
        content = mock_save.call_args[0][2]
        self.assertIn("{{Wikidata list|sparql=", content)
        self.assertIn("?item wdt:P400 wd:Q751719", content)
        self.assertIn("|columns=label,P136,P178", content)
        summary = mock_save.call_args[0][1]
        self.assertIn(
            "[[Wikidata:WikiProject Video games/Statistics/Platform]]", summary
        )

    def test_skips_existing_page(self, mock_page_cls, mock_save):
        self._make_local_page(mock_page_cls, exists=True)
        grouping = ItemGrouping(
            count=10, title="Q751719", grouping_link="Foo/Game Gear"
        )
        self.creator.create_pages([grouping])

        mock_save.assert_not_called()

    def test_skips_external_links(self, mock_page_cls, mock_save):
        grouping = ItemGrouping(
            count=10,
            title="Q123",
            grouping_link="https://scholia.toolforge.org/publisher/Q123",
        )
        self.creator.create_pages([grouping])

        mock_page_cls.assert_not_called()

    def test_skips_no_group_grouping(self, mock_page_cls, mock_save):
        self.creator.create_pages([NoGroupGrouping(count=5)])
        mock_page_cls.assert_not_called()

    def test_skips_totals_grouping(self, mock_page_cls, mock_save):
        self.creator.create_pages([TotalsGrouping(count=100)])
        mock_page_cls.assert_not_called()

    def test_skips_grouping_without_link(self, mock_page_cls, mock_save):
        self.creator.create_pages([ItemGrouping(count=10, title="Q751719")])
        mock_page_cls.assert_not_called()

    def test_skips_interwiki_link(self, mock_page_cls, mock_save):
        mock_page = MagicMock()
        mock_page.site = MagicMock()  # different site object
        mock_page_cls.return_value = mock_page

        groupings = [
            ItemGrouping(count=10, title="Q1", grouping_link=":en:Page/Q1"),
            ItemGrouping(count=5, title="Q2", grouping_link=":en:Page/Q2"),
        ]
        self.creator.create_pages(groupings)

        mock_save.assert_not_called()
        mock_page_cls.assert_called_once()  # stops after first

    def test_skips_unresolvable_interwiki(self, mock_page_cls, mock_save):
        mock_page_cls.side_effect = pywikibot.exceptions.SiteDefinitionError("bad")

        groupings = [
            ItemGrouping(count=10, title="Q1", grouping_link="toolforge:foo/Q1"),
            ItemGrouping(count=5, title="Q2", grouping_link="toolforge:foo/Q2"),
        ]
        self.creator.create_pages(groupings)

        mock_save.assert_not_called()
        mock_page_cls.assert_called_once()  # stops after first failure
