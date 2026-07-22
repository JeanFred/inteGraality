#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Column types."""

import json
import os
from abc import ABC, abstractmethod

from .sparql_utils import get_label_for_variable


class ColumnSyntaxException(Exception):
    pass


class ColumnMaker:
    @staticmethod
    def make(key, title):
        current_dir = os.path.dirname(__file__)
        wikiprojects_path = os.path.join(current_dir, "wikiprojects.json")
        wikiprojects = json.load(open(wikiprojects_path, "r"))

        if key.startswith("P"):
            splitted = key.split("/")
            if splitted[-1].startswith("S"):
                if len(splitted) == 2:
                    value = None
                elif len(splitted) == 3:
                    value = splitted[1]
                    if value.startswith("P"):
                        raise ColumnSyntaxException(
                            "References on qualified statements "
                            "(e.g. P123/P789/S*) are not yet supported"
                        )
                    if value.startswith("?") and value != "?grouping":
                        raise ColumnSyntaxException(
                            "Only ?grouping is supported as a variable value, got %s"
                            % value
                        )
                else:
                    raise ColumnSyntaxException(
                        "References on qualified statements "
                        "(e.g. P123/P789/S*) are not yet supported"
                    )
                reference_syntax = splitted[-1]
                if reference_syntax == "S*":
                    return ReferenceColumn(
                        property=splitted[0], title=title, value=value
                    )
                if reference_syntax[1:].isdigit():
                    reference_property = "P" + reference_syntax[1:]
                    return ReferenceColumn(
                        property=splitted[0],
                        title=title,
                        value=value,
                        reference_check=PropertyReferenceCheck(reference_property),
                    )
                raise ColumnSyntaxException(
                    f"Unsupported reference syntax: {reference_syntax} "
                    f"(supported: S* or S followed by digits, e.g. S248)"
                )
            if len(splitted) == 3:
                (property_name, value, qualifier) = splitted
            elif len(splitted) == 2:
                (property_name, value, qualifier) = (splitted[0], None, splitted[1])
            else:
                (property_name, value, qualifier) = (key, None, None)
            if value and value.startswith("?") and value != "?grouping":
                raise ColumnSyntaxException(
                    "Only ?grouping is supported as a variable value, got %s" % value
                )
            if qualifier:
                return QualifierColumn(
                    property=property_name,
                    title=title,
                    qualifier=qualifier,
                    value=value,
                )
            return PropertyColumn(property=property_name, title=title)
        elif key.startswith("L"):
            return LabelColumn(language=key[1:])
        elif key.startswith("D"):
            return DescriptionColumn(language=key[1:])
        elif key in wikiprojects:
            wikiproject = wikiprojects.get(key)
            return SitelinkColumn(project=key, project_data=wikiproject, title=title)
        else:
            raise ColumnSyntaxException("Unknown column syntax %s" % key)


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

    def get_variable_labels_for_positive_query(self):
        """Generate SPARQL for entity labels using native SPARQL."""
        return "\n".join(get_label_for_variable("?entity", "?entityLabel")) + "\n"

    def get_variable_labels_for_negative_query(self):
        """Generate SPARQL for entity labels using native SPARQL."""
        return "\n".join(get_label_for_variable("?entity", "?entityLabel")) + "\n"

    def _get_entity_and_value_labels(self):
        """Helper for classes that need both entity and value labels."""
        return (
            "\n".join(
                get_label_for_variable("?entity", "?entityLabel")
                + get_label_for_variable("?value", "?valueLabel")
            )
            + "\n"
        )

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
        return f"""
  ?entity p:{self.property} ?statement . OPTIONAL {{ ?statement ps:{self.property} ?value }}
"""

    def get_filter_for_negative_query(self):
        return f"""
  MINUS {{
    {{?entity a wdno:{self.property} .}} UNION
    {{?entity wdt:{self.property} ?statement .}}
  }}
"""

    def get_variable_labels_for_positive_query(self):
        """Generate SPARQL for entity and value labels using native SPARQL."""
        return self._get_entity_and_value_labels()


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
            value_ref = self.value if self.value.startswith("?") else f"wd:{self.value}"
            restrict_statement_to_value = (
                f"\n  ?statement ps:{self.property} {value_ref} ."
            )
        else:
            restrict_statement_to_value = ""
        return f"""
  ?entity p:{self.property} ?statement .{restrict_statement_to_value}
  {{ ?statement pq:{self.qualifier} ?value . }}
  UNION
  {{ ?statement a wdno:{self.qualifier} . BIND("no value"@en AS ?valueLabel) }}
"""

    def get_filter_for_negative_query(self):
        if self.value:
            value_ref = self.value if self.value.startswith("?") else f"wd:{self.value}"
            restrict_statement_to_value = (
                f"\n    ?statement ps:{self.property} {value_ref} ."
            )
        else:
            restrict_statement_to_value = ""
        return f"""
  MINUS {{
    ?entity p:{self.property} ?statement .{restrict_statement_to_value}
    {{ ?statement pq:{self.qualifier} ?value . }}
    UNION
    {{ ?statement a wdno:{self.qualifier} . }}
  }}
"""


class ReferenceCheck(ABC):
    """Base class for reference check strategies."""

    @abstractmethod
    def sparql_pattern(self):
        """SPARQL pattern (using ?_unreferenced_stmt) that is true when referenced."""

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

    def key_suffix(self):
        return "S*"

    def column_label_suffix(self):
        return "📚"

    def format_html_label(self, prop_link):
        return f"{prop_link} referenced"


class PropertyReferenceCheck(ReferenceCheck):
    """S248 − statement has a reference using a specific property."""

    def __init__(self, property):
        self.property = property

    def __eq__(self, other):
        return (
            isinstance(other, PropertyReferenceCheck)
            and self.property == other.property
        )

    def sparql_pattern(self):
        """SPARQL pattern that is true when the statement has a ref with this property."""
        return f"?_unreferenced_stmt prov:wasDerivedFrom/pr:{self.property} []"

    def key_suffix(self):
        return f"S{self.property[1:]}"

    def column_label_suffix(self):
        return f"📚{{{{Property|{self.property}}}}}"

    def format_html_label(self, prop_link):
        ref_link = (
            f'<a href="https://wikidata.org/wiki/Property:{self.property}">'
            f"{self.property}</a>"
        )
        return f"{prop_link} referenced with {ref_link}"


class ReferenceColumn(PropertyColumn):
    """Column tracking whether all statements for a property are referenced."""

    def __init__(self, property, title=None, reference_check=None, value=None):
        super().__init__(property, title)
        if reference_check is None:
            reference_check = AnyReferenceCheck()
        self.reference_check = reference_check
        self.value = value

    def __eq__(self, other):
        return (
            super().__eq__(other)
            and self.reference_check == other.reference_check
            and self.value == other.value
        )

    def _value_constraint(self, stmt_var):
        """SPARQL triple restricting a statement variable to a specific value, or None."""
        if not self.value:
            return None
        value_ref = self.value if self.value.startswith("?") else f"wd:{self.value}"
        return f"{stmt_var} ps:{self.property} {value_ref} ."

    def get_key(self):
        return "/".join(
            filter(None, [self.property, self.value, self.reference_check.key_suffix()])
        )

    def get_listeria_key(self):
        return self.property

    def get_type_name(self):
        return "reference"

    def format_html_snippet(self):
        return self.reference_check.format_html_label(super().format_html_snippet())

    def get_column_label(self):
        if self.title:
            return super().get_column_label()
        return f"{{{{Property|{self.property}}}}}{self.reference_check.column_label_suffix()}"

    def get_filter_for_info(self):
        ref_pattern = self.reference_check.sparql_pattern()
        has_value_pattern = self._value_constraint("?_s")
        if has_value_pattern:
            outer_pattern = f"?entity p:{self.property} ?_s . {has_value_pattern}"
        else:
            outer_pattern = f"?entity p:{self.property} [] ."
        vc = self._value_constraint("?_unreferenced_stmt")
        value_line = f"\n      {vc}" if vc else ""
        return f"""
    {outer_pattern}
    FILTER NOT EXISTS {{
      ?entity p:{self.property} ?_unreferenced_stmt .{value_line}
      FILTER NOT EXISTS {{ {ref_pattern} }}
    }}"""

    def get_filter_for_positive_query(self):
        ref_pattern = self.reference_check.sparql_pattern()
        vc = self._value_constraint("?_unreferenced_stmt")
        value_line = f"\n    {vc}" if vc else ""
        if self.value:
            vc_statement = self._value_constraint("?statement")
            statement_value = f"\n  {vc_statement}"
        else:
            statement_value = ""
        return f"""
  ?entity p:{self.property} ?statement .
  ?statement ps:{self.property} ?value .{statement_value}
  FILTER NOT EXISTS {{
    ?entity p:{self.property} ?_unreferenced_stmt .{value_line}
    FILTER NOT EXISTS {{ {ref_pattern} }}
  }}
"""

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
        vc_unreferenced = self._value_constraint("?_unreferenced_stmt")
        unreferenced_value_line = f"\n    {vc_unreferenced}" if vc_unreferenced else ""
        vc_any = self._value_constraint("?_any_stmt")
        any_value_line = f"\n    {vc_any}" if vc_any else ""
        return f"""
  OPTIONAL {{
    ?entity p:{self.property} ?_unreferenced_stmt .{unreferenced_value_line}
    FILTER NOT EXISTS {{ {ref_pattern} }}
  }}
  OPTIONAL {{ ?entity p:{self.property} ?_any_stmt .{any_value_line} }}
  FILTER(!BOUND(?_any_stmt) || BOUND(?_unreferenced_stmt))
"""


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
        return f"""
  FILTER(EXISTS {{
    ?entity {self.get_selector()} ?lang_label.
    FILTER((LANG(?lang_label)) = "{self.language}").
  }})
"""

    def get_filter_for_negative_query(self):
        return f"""
  MINUS {{
    {{ ?entity {self.get_selector()} ?lang_label.
    FILTER((LANG(?lang_label)) = "{self.language}") }}
  }}
"""


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
        return f"""
  ?sitelink schema:about ?entity;
    schema:isPartOf <{self.url}>;
    schema:name ?value.
"""

    def get_filter_for_negative_query(self):
        return f"""
  MINUS {{
    ?sitelink schema:about ?entity;
      schema:isPartOf <{self.url}>.
  }}
"""

    def get_variable_labels_for_positive_query(self):
        """Generate SPARQL for entity and value labels using native SPARQL."""
        return self._get_entity_and_value_labels()
