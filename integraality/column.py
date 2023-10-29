#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Column configuration classes
"""

import json
import os
from enum import Enum


class GroupingType(Enum):
    YEAR = "year"


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
            if len(splitted) == 3:
                (property_name, value, qualifier) = splitted
            elif len(splitted) == 2:
                (property_name, value, qualifier) = (splitted[0], None, splitted[1])
            else:
                (property_name, value, qualifier) = (key, None, None)
            return PropertyColumn(
                property=property_name, title=title, qualifier=qualifier, value=value
            )
        elif key.startswith("L"):
            return LabelColumn(language=key[1:])
        elif key.startswith("D"):
            return DescriptionColumn(language=key[1:])
        elif key in wikiprojects:
            wikiproject = wikiprojects.get(key)
            return SitelinkColumn(project=key, title=title)
        else:
            raise ColumnSyntaxException("Unknown column syntax %s" % key)


class AbstractColumn:
    def get_info_query(self, property_statistics):
        """
        Get the usage counts for a column for the groupings

        :return: (str) SPARQL query
        """
        grouping_selector = "\n".join(property_statistics.grouping_configuration.get_grouping_selector())
        query = f"""
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {{
  ?entity {property_statistics.selector_sparql} .
{grouping_selector}
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
  MINUS {{ ?entity wdt:{property_statistics.grouping_configuration.property} _:b28. }}
  FILTER(EXISTS {{{self.get_filter_for_info()}
  }})
}}
"""
        return query


class PropertyColumn(AbstractColumn):
    def __init__(self, property, title=None, value=None, qualifier=None):
        self.property = property
        self.title = title
        self.value = value
        self.qualifier = qualifier

    def __eq__(self, other):
        return (
            self.property == other.property
            and self.title == other.title
            and self.value == other.value
            and self.qualifier == other.qualifier
        )

    def get_title(self):
        return "/".join([x for x in [self.property, self.value, self.qualifier] if x])

    def get_key(self):
        return "".join([x for x in [self.property, self.value, self.qualifier] if x])

    def get_type_name(self):
        return "property"

    def format_html_snippet(self):
        return f'<a href="https://wikidata.org/wiki/Property:{self.property}">{self.property}</a>'

    def make_column_header(self):
        if self.qualifier:
            property_link = self.qualifier
        else:
            property_link = self.property

        if self.title:
            label = f"[[Property:{property_link}|{self.title}]]"
        else:
            label = f"{{{{Property|{property_link}}}}}"
        return f'! data-sort-type="number"|{label}\n'

    def get_filter_for_info(self):
        if self.qualifier:
            property_value = f"wd:{self.value}" if self.value else "[]"
            return f"""
    ?entity p:{self.property} [ ps:{self.property} {property_value} ; pq:{self.qualifier} [] ]"""
        else:
            return f"""
    ?entity p:{self.property}[]"""

    def get_filter_for_positive_query(self):
        return f"""
  ?entity p:{self.property} ?prop . OPTIONAL {{ ?prop ps:{self.property} ?value }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
"""

    def get_filter_for_negative_query(self):
        return f"""
    {{?entity a wdno:{self.property} .}} UNION
    {{?entity wdt:{self.property} ?prop .}}
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
"""


class TextColumn(AbstractColumn):
    def __init__(self, language, title=None):
        self.language = language
        self.title = title

    def __eq__(self, other):
        return self.language == other.language and self.title == other.title

    def get_title(self):
        return self.get_key()

    def format_html_snippet(self):
        return f"{self.language} {self.get_type_name()}"

    def make_column_header(self):
        if self.title:
            text = f"{self.title}"
        else:
            text = f"{{{{#language:{self.language}}}}}"
        return f'! data-sort-type="number"|{text}\n'

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
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{self.language}". }}
"""

    def get_filter_for_negative_query(self):
        return f"""
    {{ ?entity {self.get_selector()} ?lang_label.
    FILTER((LANG(?lang_label)) = "{self.language}") }}
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
"""


class LabelColumn(TextColumn):
    def get_key(self):
        return "L%s" % self.language

    def get_selector(self):
        return "rdfs:label"

    def get_type_name(self):
        return "label"


class DescriptionColumn(TextColumn):
    def get_key(self):
        return "D%s" % self.language

    def get_selector(self):
        return "schema:description"

    def get_type_name(self):
        return "description"


class SitelinkColumn(AbstractColumn):
    def __init__(self, project, title=None):
        current_dir = os.path.dirname(__file__)
        wikiprojects_path = os.path.join(current_dir, "wikiprojects.json")
        wikiprojects = json.load(open(wikiprojects_path, "r"))
        self.project = project
        self.url = wikiprojects[project]["url"]
        self.item = wikiprojects[project]["item"]
        self.title = title

    def __eq__(self, other):
        return self.url == other.url and self.title == other.title

    def get_key(self):
        return self.project

    def get_title(self):
        return self.get_key()

    def get_type_name(self):
        return "sitelink"

    def format_html_snippet(self):
        return f'<a href="{ self.url }">{self.get_title()} {self.get_type_name()}</a>'

    def make_column_header(self):
        if self.title:
            label = f"[[{self.item}|{self.title}]]"
        else:
            label = f"{{{{Q|{self.item}}}}}"
        return f'! data-sort-type="number"|{label}\n'

    def get_filter_for_info(self):
        return f"""
    ?sitelink schema:about ?entity;
      schema:isPartOf <{self.url}>."""

    def get_filter_for_positive_query(self):
        return f"""
  ?sitelink schema:about ?entity;
    schema:isPartOf <{self.url}>;
    schema:name ?value.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
"""

    def get_filter_for_negative_query(self):
        return f"""
    ?sitelink schema:about ?entity;
      schema:isPartOf <{self.url}>.
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
"""
