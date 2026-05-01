#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Create pages linked from grouping rows, seeded with Listeria lists.
"""

import logging

import pywikibot

from .page_saving import save_to_wiki_or_local


class _NonLocalPageError(Exception):
    pass


class GroupingPageCreator:
    def __init__(self, site, selector_sparql, grouping_predicate, columns, page_title):
        self.site = site
        self.selector_sparql = selector_sparql
        self.grouping_predicate = grouping_predicate
        self.columns = columns
        self.page_title = page_title

    def create_pages(self, groupings):
        for grouping in groupings:
            if not grouping.is_linkable or not grouping.grouping_link:
                continue
            if grouping.grouping_link.startswith(("http://", "https://")):
                continue
            try:
                self._create_page_if_missing(grouping)
            except (pywikibot.exceptions.SiteDefinitionError, _NonLocalPageError):
                logging.warning(
                    f"Cannot resolve {grouping.grouping_link} as a local page, "
                    "stopping page creation"
                )
                return

    def _create_page_if_missing(self, grouping):
        page = pywikibot.Page(self.site, grouping.grouping_link)
        if page.site != self.site:
            logging.warning(
                f"Page {grouping.grouping_link} is on a different site, "
                "stopping page creation"
            )
            raise _NonLocalPageError()
        if page.exists():
            logging.debug(f"Page {grouping.grouping_link} already exists, skipping")
            return
        content = grouping.format_listeria_wikitext(
            self.selector_sparql, self.grouping_predicate, self.columns
        )
        summary = f"Create Listeria list for grouping of [[{self.page_title}]]"
        save_to_wiki_or_local(page, summary, content, minor=False)
