"""
Create pages linked from grouping rows, seeded with Listeria lists.
"""

import logging

import pywikibot

from .page_saving import save_to_wiki_or_local

logger = logging.getLogger("integraality.update")


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
        created = 0
        for index, grouping in enumerate(groupings):
            if not grouping.is_linkable or not grouping.grouping_link:
                continue
            if grouping.grouping_link.startswith(("http://", "https://")):
                continue
            try:
                if self._create_page_if_missing(grouping, index):
                    created += 1
            except (pywikibot.exceptions.SiteDefinitionError, _NonLocalPageError):
                logger.warning(
                    f"Cannot resolve {grouping.grouping_link} as a local page, "
                    "stopping page creation"
                )
                return created
        return created

    def _create_page_if_missing(self, grouping, index):
        page = pywikibot.Page(self.site, grouping.grouping_link)
        if page.site != self.site:
            logger.warning(
                f"Page {grouping.grouping_link} is on a different site, "
                "stopping page creation"
            )
            raise _NonLocalPageError()
        if page.exists():
            logger.debug(f"Page {grouping.grouping_link} already exists, skipping")
            return False
        content = grouping.format_listeria_wikitext(
            self.selector_sparql, self.grouping_predicate, self.columns
        )
        summary = f"Create Listeria list for grouping of [[{self.page_title}]]"
        logger.info(
            f"Creating page {grouping.grouping_link}",
            extra={"step_key": f"page_creation_{index}"},
        )
        save_to_wiki_or_local(page, summary, content, minor=False)
        logger.info(
            f"Created page {grouping.grouping_link}",
            extra={
                "phase": "end",
                "step_key": f"page_creation_{index}",
                "url": page.full_url(),
            },
        )
        return True
