#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Reference check strategies for ReferenceColumn."""

from abc import ABC, abstractmethod


class ReferenceCheck(ABC):
    """Base class for reference check strategies."""

    # Properties to prioritize when showing reference values in drill-down.
    # Checked in order via COALESCE.
    HIGH_PRIORITY_REF_PROPERTIES = ["P248", "P854"]

    # Properties shown only as last resort (e.g. dates, import metadata).
    LOW_PRIORITY_REF_PROPERTIES = ["P813", "P4656", "P1065"]

    @abstractmethod
    def sparql_pattern(self):
        """SPARQL pattern (using ?_unreferenced_stmt) that is true when referenced."""

    def sparql_ref_value_binding(self, stmt_var):
        """SPARQL fragment extracting reference value(s) from a statement.

        Returns (lines, vars) where:
        - lines: list of SPARQL lines to add to the WHERE body
        - vars: list of variable names (e.g. ["?refValue"]) to add to SELECT

        Returns None if no meaningful value can be shown.
        """
        return None

    def _priority_ref_value_binding(self, stmt_var):
        """Shared implementation: bind ?refValue using priority list + fallback.

        COALESCE order: priority properties > any other property > deprioritized properties.
        """
        lines = [f"{stmt_var} prov:wasDerivedFrom ?_refNode ."]
        coalesce_vars = []
        # 1. Priority properties (P248, P854)
        for prop in self.HIGH_PRIORITY_REF_PROPERTIES:
            var = f"?_refNode_{prop}"
            lines.append(f"OPTIONAL {{ ?_refNode pr:{prop} {var} . }}")
            coalesce_vars.append(var)
        # 2. Fallback: any pr: property except priority and deprioritized
        all_excluded = (
            self.HIGH_PRIORITY_REF_PROPERTIES + self.LOW_PRIORITY_REF_PROPERTIES
        )
        excluded_list = ", ".join(f"pr:{prop}" for prop in all_excluded)
        lines.append(
            f"OPTIONAL {{ ?_refNode ?_refNode_fallback_prop ?_refNode_fallback . "
            f'FILTER(STRSTARTS(STR(?_refNode_fallback_prop), "http://www.wikidata.org/prop/reference/P")) '
            f"FILTER(?_refNode_fallback_prop NOT IN ({excluded_list})) }}"
        )
        coalesce_vars.append("?_refNode_fallback")
        # 3. Deprioritized properties as last resort
        depri_list = ", ".join(
            f"pr:{prop}" for prop in self.LOW_PRIORITY_REF_PROPERTIES
        )
        lines.append(
            f"OPTIONAL {{ ?_refNode ?_refNode_depri_prop ?_refNode_deprioritized . "
            f"FILTER(?_refNode_depri_prop IN ({depri_list})) }}"
        )
        coalesce_vars.append("?_refNode_deprioritized")
        lines.append(f"BIND(COALESCE({', '.join(coalesce_vars)}) AS ?refValue)")
        # Also bind the reference property as an entity URI (wd:) for label resolution
        prop_coalesce_parts = []
        for prop in self.HIGH_PRIORITY_REF_PROPERTIES:
            prop_coalesce_parts.append(f"IF(BOUND(?_refNode_{prop}), wd:{prop}, 1/0)")
        prop_coalesce_parts.append(
            'IRI(REPLACE(STR(?_refNode_fallback_prop), "http://www.wikidata.org/prop/reference/", "http://www.wikidata.org/entity/"))'
        )
        prop_coalesce_parts.append(
            'IRI(REPLACE(STR(?_refNode_depri_prop), "http://www.wikidata.org/prop/reference/", "http://www.wikidata.org/entity/"))'
        )
        lines.append(
            f"BIND(COALESCE({', '.join(prop_coalesce_parts)}) AS ?refProperty)"
        )
        return (lines, ["?refProperty", "?refValue"])

    @abstractmethod
    def key_suffix(self):
        """Suffix for the column key (e.g. 'S*', 'S248')."""

    @abstractmethod
    def column_label_suffix(self):
        """Wikitext suffix appended after the property template in the column header."""

    @abstractmethod
    def format_html_label(self, prop_link):
        """HTML label for the queries page, given the property link."""


class AnyReferenceCheck(ReferenceCheck):
    """S* − statement has any reference (prov:wasDerivedFrom)."""

    def __eq__(self, other):
        return isinstance(other, AnyReferenceCheck)

    def sparql_pattern(self):
        """SPARQL pattern that is true when the statement IS referenced."""
        return "?_unreferenced_stmt prov:wasDerivedFrom []"

    def sparql_ref_value_binding(self, stmt_var):
        """Bind ?refValue using priority list with fallback."""
        return self._priority_ref_value_binding(stmt_var)

    def key_suffix(self):
        return "S*"

    def column_label_suffix(self):
        return "📚"

    def format_html_label(self, prop_link):
        return f"{prop_link} referenced"


class PropertyReferenceCheck(ReferenceCheck):
    """S248 or S248=Q19216625 − statement has a reference using a specific property (optionally with a specific value)."""

    def __init__(self, property, value=None):
        self.property = property
        self.value = value

    def __eq__(self, other):
        return (
            isinstance(other, PropertyReferenceCheck)
            and self.property == other.property
            and self.value == other.value
        )

    def sparql_pattern(self):
        """SPARQL pattern that is true when the statement has a ref with this property (and value)."""
        target = f"wd:{self.value}" if self.value else "[]"
        return f"?_unreferenced_stmt prov:wasDerivedFrom/pr:{self.property} {target}"

    def sparql_ref_value_binding(self, stmt_var):
        """Bind ?refValue to the reference property value."""
        if self.value:
            # Fixed value − showing it is redundant
            return None
        return (
            [f"{stmt_var} prov:wasDerivedFrom/pr:{self.property} ?refValue ."],
            ["?refValue"],
        )

    def key_suffix(self):
        suffix = f"S{self.property[1:]}"
        if self.value:
            suffix += f"={self.value}"
        return suffix

    def column_label_suffix(self):
        label = f"📚{{{{Property|{self.property}}}}}"
        if self.value:
            label += f"={{{{Q|{self.value}}}}}"
        return label

    def format_html_label(self, prop_link):
        ref_link = (
            f'<a href="https://wikidata.org/wiki/Property:{self.property}">'
            f"{self.property}</a>"
        )
        if self.value:
            value_link = (
                f'<a href="https://wikidata.org/wiki/{self.value}">{self.value}</a>'
            )
            return f"{prop_link} referenced with {ref_link}={value_link}"
        return f"{prop_link} referenced with {ref_link}"


class MultiPropertyReferenceCheck(ReferenceCheck):
    """Base for reference checks involving a list of properties (with optional values)."""

    _key_separator = NotImplemented
    _label_separator = NotImplemented
    _html_separator = NotImplemented

    def __init__(self, properties):
        """Properties is a list of (property, value) tuples, e.g. [("P248", "Q135436770"), ("P813", None)]."""
        self.properties = properties

    def __eq__(self, other):
        return type(self) is type(other) and self.properties == other.properties

    def _key_for_item(self, prop, value):
        suffix = f"S{prop[1:]}"
        if value:
            suffix += f"={value}"
        return suffix

    def _label_for_item(self, prop, value):
        label = f"{{{{Property|{prop}}}}}"
        if value:
            label += f"={{{{Q|{value}}}}}"
        return label

    def _html_for_item(self, prop, value):
        link = f'<a href="https://wikidata.org/wiki/Property:{prop}">{prop}</a>'
        if value:
            value_link = f'<a href="https://wikidata.org/wiki/{value}">{value}</a>'
            link += f"={value_link}"
        return link

    def key_suffix(self):
        return self._key_separator.join(
            self._key_for_item(prop, value) for prop, value in self.properties
        )

    def column_label_suffix(self):
        props = self._label_separator.join(
            self._label_for_item(prop, value) for prop, value in self.properties
        )
        return f"📚{props}"

    def format_html_label(self, prop_link):
        ref_links = [
            self._html_for_item(prop, value) for prop, value in self.properties
        ]
        return f"{prop_link} referenced with {self._html_separator.join(ref_links)}"


class AnyOfPropertiesReferenceCheck(MultiPropertyReferenceCheck):
    """S248;S854 − statement has a reference using any of the specified properties (OR)."""

    _key_separator = ";"
    _label_separator = "/"
    _html_separator = " / "

    def sparql_pattern(self):
        """SPARQL pattern that is true when the statement has a ref with any of the properties."""
        lines = ["?_unreferenced_stmt prov:wasDerivedFrom ?_ref ."]
        union_parts = []
        for prop, value in self.properties:
            target = f"wd:{value}" if value else "[]"
            union_parts.append(f"{{ ?_ref pr:{prop} {target} }}")
        lines.append(" UNION ".join(union_parts))
        return "\n".join(lines)

    def sparql_ref_value_binding(self, stmt_var):
        """Bind ?refValue using COALESCE over all listed properties (in order)."""
        coalesce_vars = []
        lines = [f"{stmt_var} prov:wasDerivedFrom ?_refNode ."]
        for i, (prop, value) in enumerate(self.properties):
            if value:
                continue  # Fixed value, skip
            var = f"?_refNode_val_{i}"
            lines.append(f"OPTIONAL {{ ?_refNode pr:{prop} {var} . }}")
            coalesce_vars.append(var)
        if not coalesce_vars:
            return None
        lines.append(f"BIND(COALESCE({', '.join(coalesce_vars)}) AS ?refValue)")
        return (lines, ["?refValue"])


class AllPropertiesReferenceCheck(MultiPropertyReferenceCheck):
    """S248+S304 − reference node has all of the specified properties (AND)."""

    _key_separator = "+"
    _label_separator = "+"
    _html_separator = " + "

    def sparql_pattern(self):
        """SPARQL pattern: a single ref node has all listed properties."""
        lines = ["?_unreferenced_stmt prov:wasDerivedFrom ?_ref ."]
        for prop, value in self.properties:
            target = f"wd:{value}" if value else "[]"
            lines.append(f"?_ref pr:{prop} {target} .")
        return "\n".join(lines)

    def sparql_ref_value_binding(self, stmt_var):
        """Bind a variable for each non-fixed property value on the reference node."""
        lines = [f"{stmt_var} prov:wasDerivedFrom ?_refNode ."]
        vars = []
        for prop, value in self.properties:
            if not value:
                var = f"?ref_{prop}"
                lines.append(f"?_refNode pr:{prop} {var} .")
                vars.append(var)
        if not vars:
            return None  # All properties have fixed values
        return (lines, vars)


class GoodReferenceCheck(ReferenceCheck):
    """S! − statement has a reference that is not from a known-subpar source."""

    BAD_PROPERTIES = ["P143", "P3452", "P887"]

    def __eq__(self, other):
        return isinstance(other, GoodReferenceCheck)

    def sparql_pattern(self):
        """SPARQL pattern: ref exists and none of the subpar properties are used."""
        lines = ["?_unreferenced_stmt prov:wasDerivedFrom ?_ref ."]
        for prop in self.BAD_PROPERTIES:
            lines.append(f"FILTER NOT EXISTS {{ ?_ref pr:{prop} [] }}")
        return "\n".join(lines)

    def sparql_ref_value_binding(self, stmt_var):
        """Bind ?refValue using priority list with fallback."""
        return self._priority_ref_value_binding(stmt_var)

    def key_suffix(self):
        return "S!"

    def column_label_suffix(self):
        return "📚✓"

    def format_html_label(self, prop_link):
        return f"{prop_link} well-referenced"
