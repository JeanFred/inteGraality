import os
import unittest
from unittest.mock import call, patch

import pywikibot

from .. import page_saving


class PageSavingTest(unittest.TestCase):
    def setUp(self):
        patcher = patch("pywikibot.ItemPage", autospec=True)
        self.mock_page = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_page.site = "Site"
        self.mock_page.namespace.return_value.custom_prefix.return_value = "Prefix"
        self.mock_page.title.return_value = "Title"

    @patch.dict(os.environ, {"LOCAL_WRITE_PATH": "/path/to/"})
    def test_to_local(self):
        with patch("builtins.open") as m:
            page_saving.save_to_wiki_or_local(self.mock_page, "Update", "Lorem ipsum")

            m.assert_has_calls(
                [
                    call(b"/path/to/[Site][Prefix]Title.wiki", "w", encoding="utf-8"),
                    call().__enter__(),
                    call().__enter__().write("#summary: Update\n---------------\n"),
                    call().__enter__().write("Lorem ipsum"),
                    call().__exit__(None, None, None),
                ]
            )

    def test_to_wiki(self):
        page_saving.save_to_wiki_or_local(self.mock_page, "Update page", "Lorem ipsum")

    def test_to_wiki_returns_new_revision_id(self):
        # A real edit advances latest_revision_id from its pre-save value; put()
        # simulates editpage setting the new oldid from the API response.
        self.mock_page.latest_revision_id = 111
        self.mock_page.put.side_effect = lambda **kwargs: setattr(
            self.mock_page, "latest_revision_id", 987654
        )
        result = page_saving.save_to_wiki_or_local(
            self.mock_page, "Update page", "Lorem ipsum"
        )
        self.assertEqual(result, 987654)

    def test_to_wiki_null_edit_returns_none(self):
        # A null edit produces no revision: pywikibot leaves latest_revision_id
        # untouched, so the unchanged id must map to None (not the stale oldid,
        # which would collide on uq_revision when recorded).
        self.mock_page.latest_revision_id = 987654
        self.mock_page.put.side_effect = lambda **kwargs: None  # no advance
        result = page_saving.save_to_wiki_or_local(
            self.mock_page, "Update page", "Lorem ipsum"
        )
        self.assertIsNone(result)

    @patch("pywikibot.warning")
    def test_to_wiki_error(self, mock_warning):
        self.mock_page.put.side_effect = pywikibot.exceptions.PageSaveRelatedError(
            self.mock_page
        )
        result = page_saving.save_to_wiki_or_local(
            self.mock_page, "Update page", "Lorem ipsum"
        )
        self.assertTrue(mock_warning.called)
        self.assertIsNone(result)
