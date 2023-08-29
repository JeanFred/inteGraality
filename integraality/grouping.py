#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Grouping configuration classes
"""


class AbstractGroupingConfiguration:
    def __init__(self, higher_grouping=None, grouping_threshold=0):
        self.higher_grouping = higher_grouping
        self.grouping_threshold = grouping_threshold

    def get_grouping_information_query(self, selector_sparql):
        query = []
        query.extend(
            [
                "\n"
                f"SELECT ?grouping {self.get_select_for_higher_grouping()}(COUNT(DISTINCT ?entity) as ?count) WHERE {{",
                f"  ?entity {selector_sparql} .",
            ]
        )
        query.extend(self.get_grouping_selector())
        query.extend(self.get_higher_grouping_selector())
        query.extend(
            [
                f"HAVING (?count >= {self.grouping_threshold})",
                "ORDER BY DESC(?count)",
                "LIMIT 1000",
                "",
            ]
        )
        return "\n".join(query)

    def get_select_for_higher_grouping(self):
        if self.higher_grouping:
            return "(SAMPLE(?_higher_grouping) as ?higher_grouping) "
        else:
            return ""

    def get_higher_grouping_selector(self):
        if self.higher_grouping:
            return [
                f"  OPTIONAL {{ ?grouping {self.higher_grouping} ?_higher_grouping }}.",
                "} GROUP BY ?grouping ?higher_grouping",
            ]
        else:
            return ["} GROUP BY ?grouping"]

    def get_grouping_selector(self):
        raise NotImplementedError


class PropertyGroupingConfiguration(AbstractGroupingConfiguration):
    def __init__(self, property, higher_grouping=None, grouping_threshold=20):
        super().__init__(higher_grouping=higher_grouping, grouping_threshold=grouping_threshold)
        self.property = property

    def __eq__(self, other):
        return (
            self.property == other.property
            and self.higher_grouping == other.higher_grouping
            and self.grouping_threshold == other.grouping_threshold
        )


class ItemGroupingConfiguration(PropertyGroupingConfiguration):
    def __init__(self, property, higher_grouping=None, grouping_threshold=20):
        super().__init__(property=property, higher_grouping=higher_grouping, grouping_threshold=grouping_threshold)

    def get_grouping_selector(self):
        return [f"  ?entity wdt:{self.property} ?grouping ."]


class YearGroupingConfiguration(PropertyGroupingConfiguration):
    def __init__(self, property, grouping_threshold=20):
        super().__init__(property=property, grouping_threshold=grouping_threshold)

    def get_grouping_selector(self):
        return [
            f"  ?entity wdt:{self.property} ?date .",
            "  BIND(YEAR(?date) as ?grouping) .",
        ]
