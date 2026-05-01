#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Grouping configuration classes
"""

import collections
import re

from .grouping_link import GroupingLinkMaker
from .line import ItemGrouping, SitelinkGrouping, UnknownValueGrouping, YearGrouping
from .sparql_utils import UNKNOWN_VALUE_PREFIX, QueryException


class UnsupportedGroupingConfigurationException(Exception):
    pass


class AbstractGroupingType:
    """Base class for grouping type strategies."""

    line_type = None

    def get_grouping_selector(self, predicate):
        raise NotImplementedError

    def post_process(self, groupings):
        return groupings

    @staticmethod
    def parse_groupings(groupings_string):
        raise NotImplementedError

    @staticmethod
    def get_values_clause(explicit_groupings):
        raise NotImplementedError


class ItemGroupingType(AbstractGroupingType):
    line_type = ItemGrouping

    def get_grouping_selector(self, predicate):
        return [f"  ?entity {predicate} ?grouping ."]

    @staticmethod
    def parse_groupings(groupings_string):
        return [
            g.strip()
            for g in groupings_string.split(",")
            if re.match(r"^Q\d+$", g.strip())
        ]

    @staticmethod
    def get_values_clause(explicit_groupings):
        if not explicit_groupings:
            return []
        values = " ".join([f"wd:{g}" for g in explicit_groupings])
        return [f"  VALUES ?grouping {{ {values} }}"]


class YearGroupingType(AbstractGroupingType):
    line_type = YearGrouping
    MAX_GROUPINGS = 100

    def get_grouping_selector(self, predicate):
        return [
            f"  ?entity {predicate} ?date .",
            "  BIND(YEAR(?date) as ?grouping) .",
        ]

    def post_process(self, groupings):
        return self._rebin_if_needed(groupings)

    def _rebin_if_needed(self, groupings):
        """Rebin year groupings to a coarser resolution if there are too many."""
        keys = [key for key in groupings.keys() if key != UnknownValueGrouping.MARKER]

        time_span = 1
        while len(set(int(key) // time_span for key in keys)) > self.MAX_GROUPINGS:
            time_span *= 10

        if time_span == 1:
            return groupings

        rebinned = collections.OrderedDict()

        for key, grouping in groupings.items():
            if key == UnknownValueGrouping.MARKER:
                rebinned[key] = grouping
                continue

            new_title = str((int(grouping.title) // time_span) * time_span)
            new_grouping = YearGrouping(
                title=new_title,
                count=grouping.count,
                cells=grouping.cells.copy(),
                grouping_link=grouping.grouping_link,
                higher_grouping=grouping.higher_grouping,
                time_span=time_span,
            )
            rebinned_key = new_grouping.get_key()

            if rebinned_key in rebinned:
                rebinned[rebinned_key].count += grouping.count
                for cell_key, cell_value in grouping.cells.items():
                    rebinned[rebinned_key].cells[cell_key] = (
                        rebinned[rebinned_key].cells.get(cell_key, 0) + cell_value
                    )
            else:
                rebinned[rebinned_key] = new_grouping

        return rebinned

    @staticmethod
    def parse_groupings(groupings_string):
        return [
            int(g.strip()) for g in groupings_string.split(",") if g.strip().isdigit()
        ]

    @staticmethod
    def get_values_clause(explicit_groupings):
        if not explicit_groupings:
            return []
        values = " ".join([str(g) for g in explicit_groupings])
        return [f"  VALUES ?grouping {{ {values} }}"]


class SitelinkGroupingType(AbstractGroupingType):
    line_type = SitelinkGrouping

    def get_grouping_selector(self, predicate):
        return [
            f"  ?entity {predicate} ?sitelink.",
            "  ?sitelink schema:isPartOf ?grouping.",
        ]

    @staticmethod
    def parse_groupings(groupings_string):
        import json
        import os

        current_dir = os.path.dirname(__file__)
        wikiprojects_path = os.path.join(current_dir, "wikiprojects.json")
        wikiprojects = json.load(open(wikiprojects_path, "r"))
        codes = [g.strip() for g in groupings_string.split(",")]
        return [wikiprojects[code]["url"] for code in codes if code in wikiprojects]

    @staticmethod
    def get_values_clause(explicit_groupings):
        if not explicit_groupings:
            return []
        values = " ".join([f"<{url}>" for url in explicit_groupings])
        return [f"  VALUES ?grouping {{ {values} }}"]


DATATYPE_TO_GROUPING_TYPE = {
    "http://www.w3.org/2001/XMLSchema#dateTime": YearGroupingType,
}


class GroupingConfigurationMaker:
    @staticmethod
    def make(
        grouping_property,
        higher_grouping,
        grouping_threshold,
        base_grouping_link=None,
        explicit_groupings=None,
    ):
        if grouping_property == "schema:about":
            parsed_groupings = (
                SitelinkGroupingType.parse_groupings(explicit_groupings)
                if explicit_groupings
                else None
            )
            return GroupingConfiguration(
                predicate="^schema:about",
                higher_grouping=higher_grouping,
                grouping_threshold=grouping_threshold,
                explicit_groupings=parsed_groupings,
                grouping_type=SitelinkGroupingType(),
            )
        if re.match(r"^P\d+", grouping_property):
            predicate = f"wdt:{grouping_property}"
        else:
            predicate = grouping_property
        return GroupingConfiguration(
            predicate=predicate,
            grouping_link_type=GroupingLinkMaker.make(base_grouping_link),
            higher_grouping=higher_grouping,
            grouping_threshold=grouping_threshold,
            raw_explicit_groupings=explicit_groupings,
        )


class GroupingConfiguration:
    def __init__(
        self,
        predicate,
        higher_grouping=None,
        grouping_link_type=None,
        grouping_threshold=20,
        explicit_groupings=None,
        grouping_type=None,
        raw_explicit_groupings=None,
    ):
        self.predicate = predicate
        self.higher_grouping = higher_grouping
        self.grouping_link_type = grouping_link_type or GroupingLinkMaker.make(None)
        self.grouping_threshold = grouping_threshold
        self.explicit_groupings = explicit_groupings
        self.grouping_type = grouping_type
        self._raw_explicit_groupings = raw_explicit_groupings

    @property
    def line_type(self):
        return self.grouping_type.line_type

    def __eq__(self, other):
        return (
            self.predicate == other.predicate
            and self.higher_grouping == other.higher_grouping
            and self.grouping_link_type == other.grouping_link_type
            and self.grouping_threshold == other.grouping_threshold
            and self.explicit_groupings == other.explicit_groupings
        )

    def get_predicate(self):
        return self.predicate

    def get_grouping_selector(self):
        return self.grouping_type.get_grouping_selector(self.get_predicate())

    def post_process(self, groupings):
        return self.grouping_type.post_process(groupings)

    def format_predicate_html(self):
        if isinstance(self.grouping_type, SitelinkGroupingType):
            return "sitelink"
        match = re.match(r"^wdt:(P\d+)", self.predicate)
        if match:
            prop = match.group(1)
            return f'<a href="https://wikidata.org/wiki/Property:{prop}">{prop}</a>'
        return f"<tt>{self.predicate}</tt>"

    def get_values_clause(self):
        return self.grouping_type.get_values_clause(self.explicit_groupings)

    def get_grouping_information_query(self, selector_sparql):
        query = []

        outer_selects = [
            "?grouping",
            self.get_select_for_higher_grouping(),
            self.grouping_link_type.get_select_clause(),
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
        query.extend([f"    {line}" for line in self.get_values_clause()])
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
            self.grouping_link_type.get_sparql_fragment()
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

    def get_higher_grouping_selector(self):
        if self.higher_grouping:
            return [
                f"  OPTIONAL {{ ?grouping {self.higher_grouping} ?_higher_grouping }}.",
            ]
        else:
            return []

    def _detect_grouping_type(self, selector_sparql, sparql_query_engine):
        """Detect the grouping type by querying the datatype of values."""
        query = (
            f"SELECT (DATATYPE(?value) AS ?datatype) WHERE {{\n"
            f"  ?entity {selector_sparql} .\n"
            f"  ?entity {self.predicate} ?value .\n"
            f"}} LIMIT 1"
        )
        result = sparql_query_engine.select(query)
        if not result:
            raise QueryException(
                f"No values found for predicate {self.predicate}, cannot detect grouping type.",
                query=query,
            )
        datatype = result[0].get("datatype", "")
        if not datatype:
            return ItemGroupingType()
        grouping_type_class = DATATYPE_TO_GROUPING_TYPE.get(datatype)
        if grouping_type_class:
            return grouping_type_class()
        raise UnsupportedGroupingConfigurationException(
            f"Predicate {self.predicate} has datatype {datatype} which is not supported."
        )

    def _resolve_type(self, selector_sparql, sparql_query_engine):
        """Detect grouping type via SPARQL if not already set."""
        if self.grouping_type is None:
            self.grouping_type = self._detect_grouping_type(
                selector_sparql, sparql_query_engine
            )
            if self._raw_explicit_groupings:
                self.explicit_groupings = self.grouping_type.parse_groupings(
                    self._raw_explicit_groupings
                )

    def get_grouping_information(self, selector_sparql, sparql_query_engine):
        """
        Get all groupings and their counts.

        :return: List of Grouping objects
        """
        query = self.get_grouping_information_query(selector_sparql)
        groupings = collections.OrderedDict()

        try:
            queryresult = sparql_query_engine.select(query)

            if not queryresult:
                raise QueryException(
                    "No result when querying groupings."
                    "Please investigate the 'all groupings' debug query in the dashboard header.",
                    query=query,
                )

        except QueryException as e:
            raise QueryException(
                "The Wikidata Query Service timed out when fetching groupings."
                "You might be trying to do something too expensive."
                "Please investigate the 'all groupings' debug query in the dashboard header.",
                query=query,
            ) from e

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

                grouping_link = self.grouping_link_type.resolve(qid, resultitem)

                property_grouping = self.line_type(
                    title=qid,
                    count=int(resultitem.get("count")),
                    grouping_link=grouping_link,
                    higher_grouping=higher_grouping,
                )
                groupings[property_grouping.get_key()] = property_grouping

        if unknown_value_count:
            unknown_link = self.grouping_link_type.resolve("UNKNOWN_VALUE", {})
            unknown_value_grouping = UnknownValueGrouping(
                unknown_value_count, grouping_link=unknown_link
            )
            groupings[unknown_value_grouping.get_key()] = unknown_value_grouping

        return groupings
