#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Column types."""

import json
import os
from abc import ABC, abstractmethod


class ColumnSyntaxException(Exception):
    pass


def _format_value_sparql(value):
    """Format a value as a SPARQL term: variable as-is, QID with wd: prefix."""
    return value if value.startswith("?") else f"wd:{value}"


class ColumnMaker:
    @staticmethod
    def _load_wikiprojects():
        current_dir = os.path.dirname(__file__)
        wikiprojects_path = os.path.join(current_dir, "wikiprojects.json")
        return json.load(open(wikiprojects_path, "r"))

    @staticmethod
    def make(key, title):
        if key.startswith("P"):
            return ColumnMaker._make_property_column(key, title)
        elif key.startswith("L"):
            return LabelColumn(language=key[1:])
        elif key.startswith("D"):
            return DescriptionColumn(language=key[1:])
        else:
            wikiprojects = ColumnMaker._load_wikiprojects()
            if key in wikiprojects:
                return SitelinkColumn(
                    project=key, project_data=wikiprojects[key], title=title
                )
            raise ColumnSyntaxException(f"Unknown column syntax {key}")

    @staticmethod
    def _make_property_column(key, title):
        splitted = key.split("/")

        if splitted[-1].startswith("S"):
            return ColumnMaker._make_reference_column(splitted, title)

        if len(splitted) == 3:
            (property_name, value, qualifier) = splitted
        elif len(splitted) == 2:
            (property_name, value, qualifier) = (splitted[0], None, splitted[1])
        else:
            (property_name, value, qualifier) = (splitted[0], None, None)
        if value:
            ColumnMaker._validate_value(value)

        if qualifier:
            return QualifierColumn(
                property=property_name,
                title=title,
                qualifier=qualifier,
                value=value,
            )
        return PropertyColumn(property=property_name, title=title)

    @staticmethod
    def _make_reference_column(splitted, title):
        """Build a ReferenceColumn from slash-split parts ending with S..."""
        property_name, value, qualifier, ref_syntax = (
            ColumnMaker._parse_reference_column_parts(splitted)
        )
        reference_check = ColumnMaker._parse_reference_check(ref_syntax)
        return ReferenceColumn(
            property=property_name,
            title=title,
            value=value,
            qualifier=qualifier,
            reference_check=reference_check,
        )

    @staticmethod
    def _parse_reference_column_parts(splitted):
        """Extract (property, value, qualifier, reference_syntax) from split parts."""
        ref_syntax = splitted[-1]
        if len(splitted) == 2:
            return splitted[0], None, None, ref_syntax
        elif len(splitted) == 3:
            middle = splitted[1]
            if middle.startswith("P"):
                return splitted[0], None, middle, ref_syntax
            else:
                ColumnMaker._validate_value(middle)
                return splitted[0], middle, None, ref_syntax
        elif len(splitted) == 4:
            value, qualifier = splitted[1], splitted[2]
            ColumnMaker._validate_value(value)
            if not qualifier.startswith("P"):
                raise ColumnSyntaxException(
                    f"Expected qualifier property, got {qualifier}"
                )
            return splitted[0], value, qualifier, ref_syntax
        else:
            raise ColumnSyntaxException(
                f"Too many parts in reference column syntax: {'/'.join(splitted)}"
            )

    @staticmethod
    def _validate_value(value):
        """Raise if a value placeholder is not the supported ?grouping variable."""
        if value.startswith("?") and value != "?grouping":
            raise ColumnSyntaxException(
                f"Only ?grouping is supported as a variable value, got {value}"
            )

    @staticmethod
    def _parse_reference_check(syntax):
        """Parse a reference syntax string (e.g. 'S*', 'S248', 'S248=Q123') into a ReferenceCheck."""
        if syntax == "S*":
            return AnyReferenceCheck()
        if syntax == "S!":
            return GoodReferenceCheck()
        if syntax[1:].isdigit():
            return PropertyReferenceCheck("P" + syntax[1:])
        if "=" in syntax and ";" not in syntax and "+" not in syntax:
            return ColumnMaker._parse_value_constrained_reference(syntax)
        if ";" in syntax:
            parts = [ColumnMaker._parse_reference_part(p) for p in syntax.split(";")]
            return AnyOfPropertiesReferenceCheck(parts)
        if "+" in syntax:
            parts = [ColumnMaker._parse_reference_part(p) for p in syntax.split("+")]
            return AllPropertiesReferenceCheck(parts)
        raise ColumnSyntaxException(
            f"Unsupported reference syntax: {syntax} "
            f"(supported: S*, S!, S followed by digits, "
            f"S=value e.g. S248=Q19216625, "
            f"semicolon-separated e.g. S248;S854, "
            f"or plus-separated e.g. S248+S304)"
        )

    @staticmethod
    def _parse_value_constrained_reference(syntax):
        """Parse S248=Q19216625 into a PropertyReferenceCheck with a value constraint."""
        ref_prop_part, ref_value = syntax.split("=", 1)
        if not ref_prop_part.startswith("S") or not ref_prop_part[1:].isdigit():
            raise ColumnSyntaxException(
                f"Invalid reference property in value syntax: {ref_prop_part}"
            )
        if not ref_value.startswith("Q") or not ref_value[1:].isdigit():
            raise ColumnSyntaxException(
                f"Invalid reference value: {ref_value} (expected Q followed by digits)"
            )
        return PropertyReferenceCheck("P" + ref_prop_part[1:], ref_value)

    @staticmethod
    def _parse_reference_part(part):
        """Parse a single part of a multi-property reference syntax.

        Returns a (property, value) tuple, e.g. ("P248", None) or ("P248", "Q135436770").
        """
        if "=" in part:
            ref_prop_part, ref_value = part.split("=", 1)
            if not ref_prop_part.startswith("S") or not ref_prop_part[1:].isdigit():
                raise ColumnSyntaxException(
                    f"Invalid reference property in list: {ref_prop_part}"
                )
            if not ref_value.startswith("Q") or not ref_value[1:].isdigit():
                raise ColumnSyntaxException(
                    f"Invalid reference value in list: {ref_value} "
                    f"(expected Q followed by digits)"
                )
            return ("P" + ref_prop_part[1:], ref_value)
        else:
            if not part.startswith("S") or not part[1:].isdigit():
                raise ColumnSyntaxException(
                    f"Invalid reference property in list: {part}"
                )
            return ("P" + part[1:], None)


class AbstractColumn:
    def get_info_query(self, property_statistics):
        """
        Get the usage counts for a column for the groupings

        :return: (str) SPARQL query
        """
        grouping_selector = "\n".join(
            property_statistics.grouping_configuration.get_grouping_selector()
        )
        values_clause_lines = (
            property_statistics.grouping_configuration.get_values_clause()
        )
        values_clause = (
            "\n" + "\n".join(values_clause_lines) if values_clause_lines else ""
        )
        query = f"""
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {{
  ?entity {property_statistics.selector_sparql} .
{grouping_selector}{values_clause}
  FILTER(EXISTS {{{self.get_filter_for_info()}
  }})
}}
GROUP BY ?grouping
HAVING (?count >= {property_statistics.property_threshold})
ORDER BY DESC(?count)
LIMIT 1000
"""
        return query

    def get_totals_query(self, property_statistics):
        """
        Get the totals of entities with the column set.
        :return: (str) SPARQL query
        """
        query = f"""
SELECT (COUNT(*) as ?count) WHERE {{
  ?entity {property_statistics.selector_sparql}
  FILTER(EXISTS {{{self.get_filter_for_info()}
  }})
}}
"""
        return query

    def get_info_no_grouping_query(self, property_statistics):
        """
        Get the usage counts for a column without a grouping

        :return: (str) SPARQL query
        """
        query = f"""
SELECT (COUNT(*) AS ?count) WHERE {{
  ?entity {property_statistics.selector_sparql} .
  MINUS {{ ?entity {property_statistics.grouping_configuration.get_predicate()} _:b28. }}
  FILTER(EXISTS {{{self.get_filter_for_info()}
  }})
}}
"""
        return query

    def make_column_header(self):
        return f'! data-sort-type="number"|{self.get_column_label()}\n'


class PropertyColumn(AbstractColumn):
    def __init__(self, property, title=None):
        self.property = property
        self.title = title

    def __eq__(self, other):
        return self.property == other.property and self.title == other.title

    def get_key(self):
        return self.property

    def get_listeria_key(self):
        return self.get_key()

    def get_type_name(self):
        return "property"

    def format_html_snippet(self):
        return f'<a href="https://wikidata.org/wiki/Property:{self.property}">{self.property}</a>'

    def get_column_label(self):
        if self.title:
            return f"[[Property:{self.property}|{self.title}]]"
        return f"{{{{Property|{self.property}}}}}"

    def get_filter_for_info(self):
        return f"""
    ?entity p:{self.property}[]"""

    def get_filter_for_positive_query(self):
        return (
            f"""
  ?entity p:{self.property} ?statement . OPTIONAL {{ ?statement ps:{self.property} ?value }}
""",
            ["?entity", "?value"],
        )

    def get_filter_for_negative_query(self):
        return (
            f"""
  MINUS {{
    {{?entity a wdno:{self.property} .}} UNION
    {{?entity wdt:{self.property} ?statement .}}
  }}
""",
            ["?entity"],
        )


class QualifierColumn(PropertyColumn):
    def __init__(self, property, qualifier, value=None, title=None):
        super().__init__(property, title)
        self.qualifier = qualifier
        self.value = value

    def __eq__(self, other):
        return (
            super().__eq__(other)
            and self.qualifier == other.qualifier
            and self.value == other.value
        )

    def get_key(self):
        return "/".join([x for x in [self.property, self.value, self.qualifier] if x])

    def get_column_label(self):
        if self.title:
            return f"[[Property:{self.qualifier}|{self.title}]]"
        return f"{{{{Property|{self.qualifier}}}}}"

    def get_filter_for_info(self):
        if not self.value:
            property_value = "[]"
        elif self.value.startswith("?"):
            property_value = self.value
        else:
            property_value = f"wd:{self.value}"
        return f"""
    ?entity p:{self.property} [ ps:{self.property} {property_value} ; pq:{self.qualifier} [] ]"""

    def get_filter_for_positive_query(self):
        if self.value:
            restrict_statement_to_value = f"\n  ?statement ps:{self.property} {_format_value_sparql(self.value)} ."
        else:
            restrict_statement_to_value = ""
        return (
            f"""
  ?entity p:{self.property} ?statement .{restrict_statement_to_value}
  {{ ?statement pq:{self.qualifier} ?value . }}
  UNION
  {{ ?statement a wdno:{self.qualifier} . BIND("no value"@en AS ?valueLabel) }}
""",
            ["?entity", "?value"],
        )

    def get_filter_for_negative_query(self):
        if self.value:
            restrict_statement_to_value = f"\n    ?statement ps:{self.property} {_format_value_sparql(self.value)} ."
        else:
            restrict_statement_to_value = ""
        return (
            f"""
  MINUS {{
    ?entity p:{self.property} ?statement .{restrict_statement_to_value}
    {{ ?statement pq:{self.qualifier} ?value . }}
    UNION
    {{ ?statement a wdno:{self.qualifier} . }}
  }}
""",
            ["?entity"],
        )


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


class ReferenceColumn(PropertyColumn):
    """Column tracking whether all statements for a property are referenced."""

    def __init__(
        self, property, title=None, reference_check=None, value=None, qualifier=None
    ):
        super().__init__(property, title)
        if reference_check is None:
            reference_check = AnyReferenceCheck()
        self.reference_check = reference_check
        self.value = value
        self.qualifier = qualifier

    def __eq__(self, other):
        return (
            super().__eq__(other)
            and self.reference_check == other.reference_check
            and self.value == other.value
            and self.qualifier == other.qualifier
        )

    def _value_constraint(self, stmt_var):
        """SPARQL triple restricting a statement variable to a specific value, or None."""
        if not self.value:
            return None
        return f"{stmt_var} ps:{self.property} {_format_value_sparql(self.value)} ."

    def _qualifier_constraint(self, stmt_var):
        """SPARQL triple restricting a statement variable to having a qualifier, or None."""
        if not self.qualifier:
            return None
        return f"{stmt_var} pq:{self.qualifier} [] ."

    def get_key(self):
        return "/".join(
            filter(
                None,
                [
                    self.property,
                    self.value,
                    self.qualifier,
                    self.reference_check.key_suffix(),
                ],
            )
        )

    def get_listeria_key(self):
        return self.property

    def get_type_name(self):
        return "reference"

    def format_html_snippet(self):
        prop_link = (
            f'<a href="https://wikidata.org/wiki/Property:{self.property}">'
            f"{self.property}</a>"
        )
        parts = [prop_link]
        if self.value:
            value_ref = self.value if self.value.startswith("?") else self.value
            parts.append(f"= {value_ref}")
        if self.qualifier:
            qualifier_link = (
                f'<a href="https://wikidata.org/wiki/Property:{self.qualifier}">'
                f"{self.qualifier}</a>"
            )
            parts.append(f"qualifier {qualifier_link}")
        base = " ".join(parts)
        return self.reference_check.format_html_label(base)

    def get_column_label(self):
        if self.title:
            return super().get_column_label()
        display_property = self.qualifier if self.qualifier else self.property
        return f"{{{{Property|{display_property}}}}}{self.reference_check.column_label_suffix()}"

    def get_filter_for_info(self):
        ref_pattern = self.reference_check.sparql_pattern()
        has_value_pattern = self._value_constraint("?_s")
        has_qualifier_pattern = self._qualifier_constraint("?_s")
        indented_ref = ref_pattern.replace("\n", "\n        ")
        if has_value_pattern or has_qualifier_pattern:
            parts = [f"?entity p:{self.property} ?_s ."]
            if has_value_pattern:
                parts.append(has_value_pattern)
            if has_qualifier_pattern:
                parts.append(has_qualifier_pattern)
            outer_pattern = "\n    ".join(parts)
        else:
            outer_pattern = f"?entity p:{self.property} [] ."
        vc = self._value_constraint("?_unreferenced_stmt")
        value_line = f"\n      {vc}" if vc else ""
        qc = self._qualifier_constraint("?_unreferenced_stmt")
        qualifier_line = f"\n      {qc}" if qc else ""
        return f"""
    {outer_pattern}
    FILTER NOT EXISTS {{
      ?entity p:{self.property} ?_unreferenced_stmt .{value_line}{qualifier_line}
      FILTER NOT EXISTS {{
        {indented_ref}
      }}
    }}"""

    def get_filter_for_positive_query(self):
        ref_pattern = self.reference_check.sparql_pattern()
        indented_ref = ref_pattern.replace("\n", "\n      ")
        vc = self._value_constraint("?_unreferenced_stmt")
        value_line = f"\n    {vc}" if vc else ""
        qc = self._qualifier_constraint("?_unreferenced_stmt")
        qualifier_line = f"\n    {qc}" if qc else ""
        if self.value:
            vc_statement = self._value_constraint("?statement")
            statement_value = f"\n  {vc_statement}"
        else:
            statement_value = ""
        if self.qualifier:
            qc_statement = self._qualifier_constraint("?statement")
            statement_qualifier = f"\n  {qc_statement}"
        else:
            statement_qualifier = ""
        # Optionally bind reference value(s) from the reference node
        ref_value_result = self.reference_check.sparql_ref_value_binding("?statement")
        if ref_value_result:
            ref_value_lines, ref_vars = ref_value_result
            ref_value_fragment = "\n".join(f"  {line}" for line in ref_value_lines)
            ref_value_fragment = f"\n{ref_value_fragment}"
            select_vars = ["?entity", "?value"] + ref_vars
        else:
            ref_value_fragment = ""
            select_vars = ["?entity", "?value"]
        return (
            f"""
  ?entity p:{self.property} ?statement .
  ?statement ps:{self.property} ?value .{statement_value}{statement_qualifier}
  FILTER NOT EXISTS {{
    ?entity p:{self.property} ?_unreferenced_stmt .{value_line}{qualifier_line}
    FILTER NOT EXISTS {{
      {indented_ref}
    }}
  }}{ref_value_fragment}
""",
            select_vars,
        )

    def get_filter_for_negative_query(self):
        # Matches items that either lack the property (or specific value) entirely,
        # or have at least one unreferenced statement:
        # - First OPTIONAL binds ?_unreferenced_stmt only if an unreferenced statement exists
        # - Second OPTIONAL binds ?_any_stmt if any matching statement exists at all
        # - FILTER keeps the item if ?_any_stmt is unbound (no property/value)
        #   or ?_unreferenced_stmt is bound (has an unreferenced statement)
        #
        # This avoids nested EXISTS inside OR (broken on WDQS)
        # and bare FILTER in UNION branches (broken on QLever).
        ref_pattern = self.reference_check.sparql_pattern()
        indented_ref = ref_pattern.replace("\n", "\n      ")
        vc_unreferenced = self._value_constraint("?_unreferenced_stmt")
        unreferenced_value_line = f"\n    {vc_unreferenced}" if vc_unreferenced else ""
        qc_unreferenced = self._qualifier_constraint("?_unreferenced_stmt")
        unreferenced_qualifier_line = (
            f"\n    {qc_unreferenced}" if qc_unreferenced else ""
        )
        vc_any = self._value_constraint("?_any_stmt")
        any_value_line = f"\n    {vc_any}" if vc_any else ""
        qc_any = self._qualifier_constraint("?_any_stmt")
        any_qualifier_line = f"\n    {qc_any}" if qc_any else ""
        # Show the statement value in the drill-down results.
        # Use explicit two-triple pattern (not property path) for QLever compatibility.
        if self.value:
            value_ref = _format_value_sparql(self.value)
            show_value = f"  OPTIONAL {{ ?entity p:{self.property} ?_show_stmt . ?_show_stmt ps:{self.property} {value_ref} . BIND({value_ref} AS ?value) }}"
        else:
            show_value = f"  OPTIONAL {{ ?entity p:{self.property} ?_show_stmt . ?_show_stmt ps:{self.property} ?value . }}"
        return (
            f"""
  OPTIONAL {{
    ?entity p:{self.property} ?_unreferenced_stmt .{unreferenced_value_line}{unreferenced_qualifier_line}
    FILTER NOT EXISTS {{
      {indented_ref}
    }}
  }}
  OPTIONAL {{ ?entity p:{self.property} ?_any_stmt .{any_value_line}{any_qualifier_line} }}
  FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
{show_value}
""",
            ["?entity", "?value"],
        )


class TextColumn(AbstractColumn):
    def __init__(self, language, title=None):
        self.language = language
        self.title = title

    def __eq__(self, other):
        return self.language == other.language and self.title == other.title

    def format_html_snippet(self):
        return f"{self.language} {self.get_type_name()}"

    def get_column_label(self):
        if self.title:
            return f"{self.title}"
        return f"{{{{#language:{self.language}}}}}"

    def get_filter_for_info(self):
        return f"""
    ?entity {self.get_selector()} ?lang_label.
    FILTER((LANG(?lang_label)) = '{self.language}')."""

    def get_filter_for_positive_query(self):
        return (
            f"""
  FILTER(EXISTS {{
    ?entity {self.get_selector()} ?lang_label.
    FILTER((LANG(?lang_label)) = "{self.language}").
  }})
""",
            ["?entity"],
        )

    def get_filter_for_negative_query(self):
        return (
            f"""
  MINUS {{
    {{ ?entity {self.get_selector()} ?lang_label.
    FILTER((LANG(?lang_label)) = "{self.language}") }}
  }}
""",
            ["?entity"],
        )


class LabelColumn(TextColumn):
    def get_key(self):
        return "L%s" % self.language

    def get_listeria_key(self):
        return f"label/{self.language}"

    def get_selector(self):
        return "rdfs:label"

    def get_type_name(self):
        return "label"


class DescriptionColumn(TextColumn):
    def get_key(self):
        return "D%s" % self.language

    def get_listeria_key(self):
        return f"description/{self.language}"

    def get_selector(self):
        return "schema:description"

    def get_type_name(self):
        return "description"

    def get_filter_for_positive_query(self):
        return (
            f"""
  ?entity schema:description ?value .
  FILTER(LANG(?value) = "{self.language}")
""",
            ["?entity", "?value"],
        )


class SitelinkColumn(AbstractColumn):
    def __init__(self, project, project_data=None, title=None):
        current_dir = os.path.dirname(__file__)
        if not project_data:
            wikiprojects_path = os.path.join(current_dir, "wikiprojects.json")
            wikiprojects = json.load(open(wikiprojects_path, "r"))
            project_data = wikiprojects[project]
        self.project = project
        self.url = project_data["url"]
        self.item = project_data["item"]
        self.title = title

    def __eq__(self, other):
        return self.url == other.url and self.title == other.title

    def get_key(self):
        return self.project

    def get_listeria_key(self):
        return None

    def get_type_name(self):
        return "sitelink"

    def format_html_snippet(self):
        return f'<a href="{self.url}">{self.get_key()} {self.get_type_name()}</a>'

    def get_column_label(self):
        if self.title:
            return f"[[{self.item}|{self.title}]]"
        return f"{{{{Q|{self.item}}}}}"

    def get_filter_for_info(self):
        return f"""
    ?sitelink schema:about ?entity;
      schema:isPartOf <{self.url}>."""

    def get_filter_for_positive_query(self):
        return (
            f"""
  ?sitelink schema:about ?entity;
    schema:isPartOf <{self.url}>;
    schema:name ?value.
""",
            ["?entity", "?value"],
        )

    def get_filter_for_negative_query(self):
        return (
            f"""
  MINUS {{
    ?sitelink schema:about ?entity;
      schema:isPartOf <{self.url}>.
  }}
""",
            ["?entity"],
        )
