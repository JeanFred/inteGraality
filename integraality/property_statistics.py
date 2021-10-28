#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Calculate and generate statistics

"""
import collections
import logging
import re
from enum import Enum

from ww import f

import pywikibot
import pywikibot.data.sparql

from statsd.defaults.env import statsd


class ColumnSyntaxException(Exception):
    pass


class ColumnConfigMaker:

    @staticmethod
    def make(key, title):
        if key.startswith('P'):
            splitted = key.split('/')
            if len(splitted) == 3:
                (property_name, value, qualifier) = splitted
            elif len(splitted) == 2:
                (property_name, value, qualifier) = (splitted[0], None, splitted[1])
            else:
                (property_name, value, qualifier) = (key, None, None)
            return PropertyConfig(property=property_name, title=title, qualifier=qualifier, value=value)
        elif key.startswith('L'):
            return LabelConfig(language=key[1:])
        elif key.startswith('D'):
            return DescriptionConfig(language=key[1:])
        else:
            raise ColumnSyntaxException("Unknown column syntax %s" % key)


class ColumnConfig:

    def get_info_query(self, property_statistics):
        """
        Get the usage counts for a column for the groupings

        :return: (str) SPARQL query
        """
        query = f("""
SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {{
  ?entity {property_statistics.selector_sparql} .""")

        if property_statistics.grouping_type == GroupingType.YEAR:
            query += f("""
  ?entity wdt:{property_statistics.grouping_property} ?date .
  BIND(YEAR(?date) as ?grouping).""")

        else:
            query += f("""
  ?entity wdt:{property_statistics.grouping_property} ?grouping .""")

        query += f("""
  FILTER(EXISTS {{{self.get_filter_for_info()}
  }})
}}
GROUP BY ?grouping
HAVING (?count >= {property_statistics.property_threshold})
ORDER BY DESC(?count)
LIMIT 1000
""")
        return query

    def get_totals_query(self, property_statistics):
        """
        Get the totals of entities with the column set.
        :return: (str) SPARQL query
        """
        query = f("""
SELECT (COUNT(*) as ?count) WHERE {{
  ?entity {property_statistics.selector_sparql}
  FILTER(EXISTS {{{self.get_filter_for_info()}
  }})
}}
""")
        return query

    def get_info_no_grouping_query(self, property_statistics):
        """
        Get the usage counts for a column without a grouping

        :return: (str) SPARQL query
        """
        query = f("""
SELECT (COUNT(*) AS ?count) WHERE {{
  ?entity {property_statistics.selector_sparql} .
  MINUS {{ ?entity wdt:{property_statistics.grouping_property} _:b28. }}
  FILTER(EXISTS {{{self.get_filter_for_info()}
  }})
}}
GROUP BY ?grouping
ORDER BY DESC (?count)
LIMIT 10
""")
        return query


class PropertyConfig(ColumnConfig):

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

    def make_column_header(self):
        if self.qualifier:
            property_link = self.qualifier
        else:
            property_link = self.property

        if self.title:
            label = f('[[Property:{property_link}|{self.title}]]')
        else:
            label = f('{{{{Property|{property_link}}}}}')
        return f('! data-sort-type="number"|{label}\n')

    def get_filter_for_info(self):
        if self.qualifier:
            return f("""
    ?entity p:{self.property} [ ps:{self.property} {self.value or '[]'} ; pq:{self.qualifier} [] ]""")
        else:
            return f("""
    ?entity p:{self.property}[]""")


class TextConfig(ColumnConfig):

    def __init__(self, language, title=None):
        self.language = language
        self.title = title

    def __eq__(self, other):
        return (
            self.language == other.language
            and self.title == other.title
        )

    def get_title(self):
        return self.get_key()

    def make_column_header(self):
        if self.title:
            text = f('{self.title}')
        else:
            text = f('{{{{#language:{self.language}}}}}')
        return f('! data-sort-type="number"|{text}\n')

    def get_filter_for_info(self):
        return f("""
    ?entity {self.get_selector()} ?lang_label.
    FILTER((LANG(?lang_label)) = '{self.language}').""")


class LabelConfig(TextConfig):

    def get_key(self):
        return 'L%s' % self.language

    def get_selector(self):
        return 'rdfs:label'


class DescriptionConfig(TextConfig):

    def get_key(self):
        return 'D%s' % self.language

    def get_selector(self):
        return 'schema:description'


class QueryException(Exception):

    def __init__(self, message, query):
        super().__init__(message)
        self.query = query


class GroupingType(Enum):
    YEAR = "year"


class PropertyStatistics:
    """
    Generate statitics

    """
    UNKNOWN_VALUE_PREFIX = "http://www.wikidata.org/.well-known/genid/"

    GROUP_MAPPING = Enum('GROUP_MAPPING', {
        'NO_GROUPING': 'None',
        'TOTALS': '',
        'UNKNOWN_VALUE': '{{int:wikibase-snakview-variations-somevalue-label}}'
    })

    TEXT_SELECTOR_MAPPING = {'L': 'rdfs:label', 'D': 'schema:description'}

    def __init__(self, selector_sparql, columns, grouping_property, grouping_type=None, higher_grouping=None, higher_grouping_type=None, stats_for_no_group=False, grouping_link=None, grouping_threshold=20, property_threshold=0):  # noqa
        """
        Set what to work on and other variables here.
        """
        site = pywikibot.Site('en', 'wikipedia')
        self.repo = site.data_repository()
        self.columns = columns
        self.grouping_property = grouping_property
        if grouping_type:
            self.grouping_type = GroupingType(grouping_type)
        else:
            self.grouping_type = None
        self.higher_grouping = higher_grouping
        self.higher_grouping_type = higher_grouping_type
        self.selector_sparql = selector_sparql
        self.stats_for_no_group = stats_for_no_group
        self.grouping_threshold = grouping_threshold
        self.property_threshold = property_threshold

        self.grouping_link = grouping_link
        self.column_data = {}
        self.cell_template = 'Integraality cell'

    @statsd.timer('property_statistics.sparql.groupings')
    def get_grouping_information(self):
        """
        Get the information for a single grouping.

        :return: Tuple of two (ordered) dictionaries.
        """
        if self.higher_grouping:
            query = f("""
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) (COUNT(DISTINCT *) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?grouping .
  OPTIONAL {{ ?grouping {self.higher_grouping} ?_higher_grouping }}.
}} GROUP BY ?grouping ?higher_grouping
HAVING (?count >= {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 1000
""")
        elif self.grouping_type == GroupingType.YEAR:
            query = f("""
SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?date .
  BIND(YEAR(?date) as ?grouping) .
}} GROUP BY ?grouping
HAVING (?count >= {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 1000
""")
        else:
            query = f("""
SELECT ?grouping (COUNT(DISTINCT *) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?grouping .
}} GROUP BY ?grouping
HAVING (?count >= {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 1000
""")
        grouping_counts = collections.OrderedDict()

        grouping_groupings = collections.OrderedDict()

        try:
            sq = pywikibot.data.sparql.SparqlQuery()
            queryresult = sq.select(query)

            if not queryresult:
                raise QueryException(
                    "No result when querying groupings."
                    "Please investigate the 'all groupings' debug query in the dashboard header.",
                    query=query
                )

        except pywikibot.exceptions.TimeoutError:

            raise QueryException(
                "The Wikidata Query Service timed out when fetching groupings."
                "You might be trying to do something too expensive."
                "Please investigate the 'all groupings' debug query in the dashboard header.",
                query=query
            )

        for resultitem in queryresult:
            if resultitem.get('grouping').startswith(self.UNKNOWN_VALUE_PREFIX):
                if self.GROUP_MAPPING.UNKNOWN_VALUE.name not in grouping_counts.keys():
                    grouping_counts[self.GROUP_MAPPING.UNKNOWN_VALUE.name] = 0
                grouping_counts[self.GROUP_MAPPING.UNKNOWN_VALUE.name] += int(resultitem.get('count'))
            else:
                qid = resultitem.get('grouping').replace(u'http://www.wikidata.org/entity/', u'')
                grouping_counts[qid] = int(resultitem.get('count'))

            if self.higher_grouping:
                value = resultitem.get('higher_grouping')
                if value:
                    value = value.replace(u'http://www.wikidata.org/entity/', u'')
                grouping_groupings[qid] = value

        return (grouping_counts, grouping_groupings)

    def get_query_for_items_for_property_positive(self, column, grouping):
        query = f("""
SELECT DISTINCT ?entity ?entityLabel ?value ?valueLabel WHERE {{
  ?entity {self.selector_sparql} .""")

        if grouping == self.GROUP_MAPPING.TOTALS:
            pass

        elif grouping == self.GROUP_MAPPING.NO_GROUPING:
            query += f("""
  MINUS {{
    ?entity wdt:{self.grouping_property} [] .
  }}""")

        elif grouping == self.GROUP_MAPPING.UNKNOWN_VALUE:
            query += f("""
  ?entity wdt:{self.grouping_property} ?grouping.
  FILTER wikibase:isSomeValue(?grouping).""")

        elif self.grouping_type == GroupingType.YEAR:
            query += f("""
  ?entity wdt:{self.grouping_property} ?date.
  BIND(YEAR(?date) as ?year).
  FILTER(?year = {grouping}).""")

        else:
            query += f("""
  ?entity wdt:{self.grouping_property} wd:{grouping} .""")

        if column.startswith('P'):
            query += f("""
  ?entity p:{column} ?prop . OPTIONAL {{ ?prop ps:{column} ?value }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
}}
""")
        elif column.startswith('L') or column.startswith('D'):

            query += f("""
  FILTER(EXISTS {{
    ?entity {self.TEXT_SELECTOR_MAPPING[column[:1]]} ?lang_label.
    FILTER((LANG(?lang_label)) = "{column[1:]}").
  }})
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{column[1:]}". }}
}}
""")

        return query

    def get_query_for_items_for_property_negative(self, column, grouping):
        query = f("""
SELECT DISTINCT ?entity ?entityLabel WHERE {{
  ?entity {self.selector_sparql} .""")

        if grouping == self.GROUP_MAPPING.TOTALS:
            query += f("""
  MINUS {{""")

        elif grouping == self.GROUP_MAPPING.NO_GROUPING:
            query += f("""
  MINUS {{
    {{?entity wdt:{self.grouping_property} [] .}} UNION""")

        elif grouping == self.GROUP_MAPPING.UNKNOWN_VALUE:
            query += f("""
  ?entity wdt:{self.grouping_property} ?grouping.
  FILTER wikibase:isSomeValue(?grouping).
  MINUS {{""")

        elif self.grouping_type == GroupingType.YEAR:
            query += f("""
  ?entity wdt:{self.grouping_property} ?date.
  BIND(YEAR(?date) as ?year).
  FILTER(?year = {grouping}).
  MINUS {{""")

        else:
            query += f("""
  ?entity wdt:{self.grouping_property} wd:{grouping} .
  MINUS {{""")

        if column.startswith('P'):
            query += f("""
    {{?entity a wdno:{column} .}} UNION
    {{?entity wdt:{column} ?prop .}}
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
}}
""")
        elif column.startswith('L') or column.startswith('D'):
            query += f("""
    {{ ?entity {self.TEXT_SELECTOR_MAPPING[column[:1]]} ?lang_label.
    FILTER((LANG(?lang_label)) = "{column[1:]}") }}
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
}}
""")

        return query

    def get_totals_no_grouping(self):
        query = f("""
SELECT (COUNT(*) as ?count) WHERE {{
  ?entity {self.selector_sparql}
  MINUS {{ ?entity wdt:{self.grouping_property} _:b28. }}
}}
""")
        return self._get_count_from_sparql(query)

    def get_totals(self):
        query = f("""
SELECT (COUNT(*) as ?count) WHERE {{
  ?entity {self.selector_sparql}
}}
""")
        return self._get_count_from_sparql(query)

    @staticmethod
    @statsd.timer('property_statistics.sparql.count')
    def _get_count_from_sparql(query):
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)
        if not queryresult:
            raise QueryException("No result when running a SPARQL query.", query=query)

        return int(queryresult[0].get('count'))

    @statsd.timer('property_statistics.sparql.grouping_counts')
    def _get_grouping_counts_from_sparql(self, query):
        result = collections.OrderedDict()
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)
        if not queryresult:
            return None
        for resultitem in queryresult:

            if resultitem.get('grouping').startswith(self.UNKNOWN_VALUE_PREFIX):
                if self.GROUP_MAPPING.UNKNOWN_VALUE.name not in result.keys():
                    result[self.GROUP_MAPPING.UNKNOWN_VALUE.name] = 0
                result[self.GROUP_MAPPING.UNKNOWN_VALUE.name] += int(resultitem.get('count'))
            else:
                qid = resultitem.get('grouping').replace(u'http://www.wikidata.org/entity/', u'')
                result[qid] = int(resultitem.get('count'))

        return result

    @staticmethod
    def _get_percentage(count, total):
        if not count:
            return 0
        return round(1.0 * count / max(total, 1) * 100, 2)

    def get_header(self):
        text = u'{| class="wikitable sortable"\n'
        colspan = 3 if self.higher_grouping else 2
        text += f('! colspan="{colspan}" |Top groupings (Minimum {self.grouping_threshold} items)\n')
        text += f('! colspan="{len(self.columns)}"|Top Properties (used at least {self.property_threshold} times per grouping)\n')  # noqa
        text += u'|-\n'

        if self.higher_grouping:
            text += u'! \n'

        text += u'! Name\n'
        text += u'! Count\n'
        for column_entry in self.columns:
            text += column_entry.make_column_header()

        return text

    def format_higher_grouping_text(self, higher_grouping_value):
        type_mapping = {
            "country": "{{Flag|%s}}" % higher_grouping_value,
        }
        if re.match(r"Q\d+", higher_grouping_value):
            higher_grouping_text = f('{{{{Q|{higher_grouping_value}}}}}')
        elif re.match(r"http://commons.wikimedia.org/wiki/Special:FilePath/(.*?)$", higher_grouping_value):
            match = re.match(r"http://commons.wikimedia.org/wiki/Special:FilePath/(.*?)$", higher_grouping_value)
            image_name = match.groups()[0]
            higher_grouping_text = f('[[File:{image_name}|center|100px]]')
            higher_grouping_value = image_name
        elif self.higher_grouping_type in type_mapping:
            higher_grouping_text = type_mapping.get(self.higher_grouping_type)
        else:
            higher_grouping_text = higher_grouping_value
        return f('| data-sort-value="{higher_grouping_value}"| {higher_grouping_text}\n')

    def make_stats_for_no_group(self):
        """
        Query the data for no_group, return the wikitext
        """
        text = u'|-\n'

        if self.higher_grouping:
            text += u'|\n'

        total_no_count = self.get_totals_no_grouping()
        text += u'| No grouping \n'
        text += f('| {total_no_count} \n')

        for column_entry in self.columns:
            column_count = self._get_count_from_sparql(column_entry.get_info_no_grouping_query(self))
            percentage = self._get_percentage(column_count, total_no_count)
            text += f('| {{{{{self.cell_template}|{percentage}|{column_count}|column={column_entry.get_title()}|grouping={self.GROUP_MAPPING.NO_GROUPING.value}}}}}\n')  # noqa

        return text

    def make_stats_for_one_grouping(self, grouping, item_count, higher_grouping):
        """
        Query the data for one group, return the wikitext.
        """
        text = u'|-\n'

        if self.higher_grouping:
            if higher_grouping:
                text += self.format_higher_grouping_text(higher_grouping)
            else:
                text += u'|\n'

        if grouping in self.GROUP_MAPPING.__members__:
            text += u'| %s\n' % (self.GROUP_MAPPING.__members__.get(grouping).value,)
        elif self.grouping_type == GroupingType.YEAR:
            text += u'| %s\n' % (grouping,)
        else:
            text += u'| {{Q|%s}}\n' % (grouping,)

        if self.grouping_link:
            try:
                group_item = pywikibot.ItemPage(self.repo, grouping)
                group_item.get()
                label = group_item.labels["en"]
            except (pywikibot.exceptions.InvalidTitle, KeyError):
                logging.info(f("Could not retrieve label for {grouping}"))
                label = grouping
            text += f('| [[{self.grouping_link}/{label}|{item_count}]] \n')
        else:
            text += f('| {item_count} \n')

        for column_entry in self.columns:
            column_entry_key = column_entry.get_key()
            try:
                column_count = self.column_data.get(column_entry_key).get(grouping)
            except AttributeError:
                column_count = 0
            if not column_count:
                column_count = 0
            percentage = self._get_percentage(column_count, item_count)
            text += f('| {{{{{self.cell_template}|{percentage}|{column_count}|column={column_entry.get_title()}|grouping={grouping}}}}}\n')  # noqa
        return text

    def make_footer(self):
        total_items = self.get_totals()
        text = u'|- class="sortbottom"\n|'
        if self.higher_grouping:
            text += u"|\n|"

        text += f('\'\'\'Totals\'\'\' <small>(all items)</small>:\n| {total_items}\n')
        for column_entry in self.columns:
            totalprop = self._get_count_from_sparql(column_entry.get_totals_query(self))
            percentage = self._get_percentage(totalprop, total_items)
            text += f('| {{{{{self.cell_template}|{percentage}|{totalprop}|column={column_entry.get_title()}}}}}\n')
        text += u'|}\n'
        return text

    @statsd.timer('property_statistics.processing')
    def retrieve_and_process_data(self):
        """
        Query the data, output wikitext
        """
        logging.info("Retrieving grouping information...")

        try:
            (groupings_counts, groupings_groupings) = self.get_grouping_information()
        except QueryException as e:
            logging.error(f('No groupings found.'))
            raise e

        logging.info(f('Grouping retrieved: {len(groupings_counts)}'))
        for column_entry in self.columns:
            column_entry_key = column_entry.get_key()
            self.column_data[column_entry_key] = self._get_grouping_counts_from_sparql(column_entry.get_info_query(self))

        text = self.get_header()

        for (grouping, item_count) in sorted(groupings_counts.items(), key=lambda t: t[1], reverse=True):
            higher_grouping = groupings_groupings.get(grouping)
            text += self.make_stats_for_one_grouping(grouping, item_count, higher_grouping)

        if self.stats_for_no_group:
            text += self.make_stats_for_no_group()

        text += self.make_footer()

        return text


def main(*args):
    """
    Main function.
    """
    columns = [
        PropertyConfig('P21'),
        PropertyConfig('P19'),
        LabelConfig('de'),
        DescriptionConfig('de'),
    ]
    logging.info("Main function...")
    stats = PropertyStatistics(
        columns=columns,
        selector_sparql=u'wdt:P31 wd:Q41960',
        grouping_property=u'P551',
        stats_for_no_group=True,
        grouping_threshold=5,
        property_threshold=1,
    )
    print(stats.retrieve_and_process_data())


if __name__ == "__main__":
    main()
