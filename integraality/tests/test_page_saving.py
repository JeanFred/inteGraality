# -*- coding: utf-8  -*-

import os
import unittest
from unittest.mock import call, patch

import page_saving


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
