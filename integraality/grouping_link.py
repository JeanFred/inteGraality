#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Grouping link strategy classes.
"""

import re

from .sparql_utils import get_label_for_variable


class GroupingLinkSyntaxException(Exception):
    pass


class GroupingLinkMaker:
    @staticmethod
    def make(base_grouping_link):
        if not base_grouping_link:
            return NoGroupingLink()

        matches = re.findall(r"\{(.*?)\}", base_grouping_link)
        if not matches:
            # Backward compat: no placeholder → append /{Len}
            return LabelGroupingLink(template=f"{base_grouping_link}/{{Len}}")

        if len(matches) > 1:
            raise GroupingLinkSyntaxException(
                "Only one placeholder is supported in grouping link"
            )

        inner = matches[0]
        if inner.startswith("L"):
            return LabelGroupingLink(template=base_grouping_link, lang=inner[1:])

        if inner == "id":
            return IdGroupingLink(template=base_grouping_link)

        raise GroupingLinkSyntaxException(
            f"Unsupported grouping link placeholder: {{{inner}}}"
        )


class AbstractGroupingLink:
    """Base class for grouping link strategies."""

    def __init__(self, template):
        self.template = template

    def get_select_clause(self):
        return ""

    def get_sparql_fragment(self):
        return ([], None)

    def get_value(self, qid, resultitem):
        raise NotImplementedError

    def resolve(self, qid, resultitem):
        value = self.get_value(qid, resultitem)
        return self.template.replace(self.placeholder, value)

    def __eq__(self, other):
        return type(self) is type(other) and self.template == other.template


class NoGroupingLink(AbstractGroupingLink):
    def __init__(self):
        super().__init__(template=None)

    def resolve(self, qid, resultitem):
        return None


class IdGroupingLink(AbstractGroupingLink):
    def __init__(self, template):
        super().__init__(template)
        self.placeholder = "{id}"

    def get_value(self, qid, resultitem):
        return qid


class LabelGroupingLink(AbstractGroupingLink):
    def __init__(self, template, lang="en"):
        super().__init__(template)
        self.lang = lang
        self.placeholder = f"{{L{lang}}}"

    def get_select_clause(self):
        return "?grouping_link_value"

    def get_sparql_fragment(self):
        return (
            get_label_for_variable("?grouping", "?grouping_link_value", self.lang),
            "?grouping_link_value",
        )

    def get_value(self, qid, resultitem):
        return resultitem.get("grouping_link_value") or qid

    def __eq__(self, other):
        return (
            type(self) is type(other)
            and self.template == other.template
            and self.lang == other.lang
        )
