#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Grouping configuration classes
"""

import collections
import re

import pywikibot.data.sparql

from line import ItemGrouping, SitelinkGrouping, UnknownValueGrouping, YearGrouping
from sparql_utils import UNKNOWN_VALUE_PREFIX, QueryException


class GroupingConfigurationSyntaxException(Exception):
    pass


class UnsupportedGroupingConfigurationException(Exception):
    pass


class GroupingConfigurationMaker:
    @staticmethod
    def make(
        repo,
        grouping_property,
        higher_grouping,
        grouping_threshold,
        base_grouping_link=None,
    ):
        if grouping_property == "schema:about":
            return SitelinkGroupingConfiguration(
                higher_grouping=higher_grouping,
                grouping_threshold=grouping_threshold,
            )
        if re.match(r"^P\d+$", grouping_property):
            property_page = pywikibot.PropertyPage(repo, grouping_property)
            property_type = property_page.get_data_for_new_entity()["datatype"]
            print(f"property_type is {property_type}")
            if property_type == "wikibase-item":
                return ItemGroupingConfiguration(
                    property=grouping_property,
                    base_grouping_link=base_grouping_link,
                    higher_grouping=higher_grouping,
                    grouping_threshold=grouping_threshold,
                )
            elif property_type == "time":
                return YearGroupingConfiguration(
                    property=grouping_property,
                    base_grouping_link=base_grouping_link,
                    grouping_threshold=grouping_threshold,
                )
            else:
                raise UnsupportedGroupingConfigurationException(
                    f"Property {grouping_property} is of type {property_type} which is not supported."
                )
        elif re.match(r"^P\d+", grouping_property):
            return PredicateGroupingConfiguration(
                predicate=f"wdt:{grouping_property}",
                base_grouping_link=base_grouping_link,
                higher_grouping=higher_grouping,
                grouping_threshold=grouping_threshold,
            )
        else:
            return PredicateGroupingConfiguration(
                predicate=grouping_property,
                base_grouping_link=base_grouping_link,
                higher_grouping=higher_grouping,
                grouping_threshold=grouping_threshold,
            )


class AbstractGroupingConfiguration:
    def __init__(
        self, higher_grouping=None, base_grouping_link=None, grouping_threshold=0
    ):
        self.higher_grouping = higher_grouping
        self.base_grouping_link = base_grouping_link
        self.grouping_threshold = grouping_threshold

    def get_grouping_information_query(self, selector_sparql):
        query = []

        outer_selects = [
            "?grouping",
            self.get_select_for_higher_grouping(),
            self.get_select_for_grouping_link_value(),
            "?count",
        ]

        inner_selects = ["?grouping", "(COUNT(DISTINCT ?entity) as ?count)"]

        query.extend(
            [
                f"\nSELECT {' '.join([x for x in outer_selects if x])} WHERE {{",
                "  {",
                f"    SELECT {' '.join(inner_selects)} WHERE {{",
                f"      ?entity {selector_sparql} .",
            ]
        )
        query.extend([f"    {line}" for line in self.get_grouping_selector()])
        query.extend(
            [
                "    }",
                "    GROUP BY ?grouping",
                f"    HAVING (?count >= {self.grouping_threshold})",
                "  }",
            ]
        )
        query.extend(self.get_higher_grouping_selector())

        (grouping_link_select, grouping_link_group_by) = (
            self.get_grouping_link_selector()
        )
        query.extend(grouping_link_select)
        query.append("}")

        if self.higher_grouping:
            group_bys = ["?grouping", grouping_link_group_by, "?count"]
            query.append(f"GROUP BY {' '.join([x for x in group_bys if x])}")

        query.extend(
            [
                "ORDER BY DESC(?count)",
                "LIMIT 1000",
                "",
            ]
        )
        return "\n".join(query)

    def get_select_for_higher_grouping(self):
        if self.higher_grouping:
            return "(SAMPLE(?_higher_grouping) as ?higher_grouping)"
        else:
            return ""

    def get_select_for_grouping_link_value(self):
        if self.base_grouping_link:
            return "?grouping_link_value"
        else:
            return ""

    def get_higher_grouping_selector(self):
        if self.higher_grouping:
            return [
                f"  OPTIONAL {{ ?grouping {self.higher_grouping} ?_higher_grouping }}.",
            ]
        else:
            return []

    def get_grouping_link_selector(self):
        if self.base_grouping_link:
            return (
                [
                    "  OPTIONAL {{",
                    "    ?grouping rdfs:label ?labelMUL.",
                    "    FILTER(lang(?labelMUL)='mul')",
                    "  }}.",
                    "  OPTIONAL {{",
                    "    ?grouping rdfs:label ?labelEN.",
                    "    FILTER(lang(?labelEN)='en')",
                    "  }}.",
                    "  BIND(COALESCE(?labelEN, ?labelMUL) AS ?grouping_link_value).",
                ],
                "?grouping_link_value",
            )
        else:
            return ([], None)

    def get_grouping_selector(self):
        raise NotImplementedError

    def get_grouping_information(self, selector_sparql):
        """
        Get all groupings and their counts.

        :return: List of Grouping objects
        """
        query = self.get_grouping_information_query(selector_sparql)
        groupings = collections.OrderedDict()

        try:
            sq = pywikibot.data.sparql.SparqlQuery()
            queryresult = sq.select(query)

            if not queryresult:
                raise QueryException(
                    "No result when querying groupings."
                    "Please investigate the 'all groupings' debug query in the dashboard header.",
                    query=query,
                )

        except (pywikibot.exceptions.TimeoutError, pywikibot.exceptions.ServerError):
            raise QueryException(
                "The Wikidata Query Service timed out when fetching groupings."
                "You might be trying to do something too expensive."
                "Please investigate the 'all groupings' debug query in the dashboard header.",
                query=query,
            )

        unknown_value_count = 0

        for resultitem in queryresult:
            if not resultitem.get("grouping") or resultitem.get("grouping").startswith(
                UNKNOWN_VALUE_PREFIX
            ):
                unknown_value_count += int(resultitem.get("count"))

            else:
                qid = resultitem.get("grouping").replace(
                    "http://www.wikidata.org/entity/", ""
                )
                if self.higher_grouping:
                    value = resultitem.get("higher_grouping")
                    if value:
                        value = value.replace("http://www.wikidata.org/entity/", "")
                    else:
                        value = ""
                    higher_grouping = value
                else:
                    higher_grouping = None

                if self.base_grouping_link:
                    value = resultitem.get("grouping_link_value")
                    if not value:
                        value = qid
                    grouping_link = f"{self.base_grouping_link}/{value}"
                else:
                    grouping_link = None

                property_grouping = self.line_type(
                    title=qid,
                    count=int(resultitem.get("count")),
                    grouping_link=grouping_link,
                    higher_grouping=higher_grouping,
                )
                groupings[property_grouping.get_key()] = property_grouping

        if unknown_value_count:
            if self.base_grouping_link:
                unknown_value_grouping = UnknownValueGrouping(
                    unknown_value_count,
                    grouping_link=f"{self.base_grouping_link}/UNKNOWN_VALUE",
                )
            else:
                unknown_value_grouping = UnknownValueGrouping(unknown_value_count)
            groupings[unknown_value_grouping.get_key()] = unknown_value_grouping

        return groupings


class PredicateGroupingConfiguration(AbstractGroupingConfiguration):
    line_type = ItemGrouping

    def __init__(
        self,
        predicate,
        higher_grouping=None,
        base_grouping_link=None,
        grouping_threshold=20,
    ):
        super().__init__(
            higher_grouping=higher_grouping,
            base_grouping_link=base_grouping_link,
            grouping_threshold=grouping_threshold,
        )
        self.predicate = predicate

    def __eq__(self, other):
        return (
            self.predicate == other.predicate
            and self.higher_grouping == other.higher_grouping
            and self.base_grouping_link == other.base_grouping_link
            and self.grouping_threshold == other.grouping_threshold
        )

    def get_predicate(self):
        return self.predicate

    def get_grouping_selector(self):
        return [f"  ?entity {self.get_predicate()} ?grouping ."]

    def format_predicate_html(self):
        return f"<tt>{self.predicate}</tt>"


class PropertyGroupingConfiguration(AbstractGroupingConfiguration):
    def __init__(
        self,
        property,
        higher_grouping=None,
        base_grouping_link=None,
        grouping_threshold=20,
    ):
        super().__init__(
            higher_grouping=higher_grouping,
            base_grouping_link=base_grouping_link,
            grouping_threshold=grouping_threshold,
        )
        self.property = property

    def __eq__(self, other):
        return (
            self.property == other.property
            and self.higher_grouping == other.higher_grouping
            and self.base_grouping_link == other.base_grouping_link
            and self.grouping_threshold == other.grouping_threshold
        )

    def get_predicate(self):
        return f"wdt:{self.property}"

    def format_predicate_html(self):
        return f'<a href="https://wikidata.org/wiki/Property:{self.property}">{self.property}</a>'


class ItemGroupingConfiguration(PropertyGroupingConfiguration):
    line_type = ItemGrouping

    def __init__(
        self,
        property,
        higher_grouping=None,
        base_grouping_link=None,
        grouping_threshold=20,
    ):
        super().__init__(
            property=property,
            higher_grouping=higher_grouping,
            base_grouping_link=base_grouping_link,
            grouping_threshold=grouping_threshold,
        )

    def get_grouping_selector(self):
        return [f"  ?entity {self.get_predicate()} ?grouping ."]


class YearGroupingConfiguration(PropertyGroupingConfiguration):
    line_type = YearGrouping

    def __init__(self, property, base_grouping_link=None, grouping_threshold=20):
        super().__init__(
            property=property,
            base_grouping_link=base_grouping_link,
            grouping_threshold=grouping_threshold,
        )

    def get_grouping_selector(self):
        return [
            f"  ?entity {self.get_predicate()} ?date .",
            "  BIND(YEAR(?date) as ?grouping) .",
        ]


class SitelinkGroupingConfiguration(AbstractGroupingConfiguration):
    line_type = SitelinkGrouping

    def __init__(self, higher_grouping=None, grouping_threshold=20):
        super().__init__(
            higher_grouping=higher_grouping, grouping_threshold=grouping_threshold
        )

    def __eq__(self, other):
        return (
            self.higher_grouping == other.higher_grouping
            and self.grouping_threshold == other.grouping_threshold
        )

    def format_predicate_html(self):
        return "sitelink"

    def get_grouping_selector(self):
        return [
            f"  ?entity {self.get_predicate()} ?sitelink.",
            "  ?sitelink schema:isPartOf ?grouping.",
        ]

    def get_predicate(self):
        return "^schema:about"
