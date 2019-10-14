#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Calculate and generate statistics

"""
import collections
import logging

from ww import f

import pywikibot
import pywikibot.data.sparql


class QueryException(Exception):
    pass


class PropertyStatistics:
    """
    Generate statitics

    """
    def __init__(self, selector_sparql, properties, grouping_property, higher_grouping=None, higher_grouping_type=None, stats_for_no_group=False, grouping_link=None, grouping_threshold=20, property_threshold=10):  # noqa
        """
        Set what to work on and other variables here.
        """
        site = pywikibot.Site('en', 'wikipedia')
        self.repo = site.data_repository()
        self.properties = properties
        self.grouping_property = grouping_property
        self.higher_grouping = higher_grouping
        self.higher_grouping_type = higher_grouping_type
        self.selector_sparql = selector_sparql
        self.stats_for_no_group = stats_for_no_group
        self.grouping_threshold = grouping_threshold
        self.property_threshold = property_threshold

        self.grouping_link = grouping_link
        self.property_data = {}
        self.cell_template = 'Coloured cell'

    def get_grouping_information(self):
        """
        Get the information for a single grouping.

        :return: Tuple of two (ordered) dictionaries.
        """
        if self.higher_grouping:
            query = f("""
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) (COUNT(DISTINCT ?entity) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?grouping .
  OPTIONAL {{ ?grouping {self.higher_grouping} ?_higher_grouping }}.
}} GROUP BY ?grouping ?higher_grouping
HAVING (?count > {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 1000
""")
        else:
            query = f("""
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?grouping .
}} GROUP BY ?grouping
HAVING (?count > {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 1000
""")
        grouping_counts = collections.OrderedDict()

        grouping_groupings = collections.OrderedDict()

        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)

        if not queryresult:
            raise QueryException("No result when querying groupings.")

        for resultitem in queryresult:
            qid = resultitem.get('grouping').replace(u'http://www.wikidata.org/entity/', u'')
            grouping_counts[qid] = int(resultitem.get('count'))

            if self.higher_grouping:
                value = resultitem.get('higher_grouping')
                if value:
                    value = value.replace(u'http://www.wikidata.org/entity/', u'')
                grouping_groupings[qid] = value

        return (grouping_counts, grouping_groupings)

    def get_property_info(self, property):
        """
        Get the usage counts for a property for the groupings

        :param prop: Wikidata Pid of the property
        :return: (Ordered) dictionary with the counts per grouping
        """
        query = f("""
SELECT ?grouping (COUNT(DISTINCT ?entity) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?grouping .
  FILTER EXISTS {{ ?entity p:{property} [] }} .
}} GROUP BY ?grouping
HAVING (?count > {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 1000
""")
        result = collections.OrderedDict()
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)
        if not queryresult:
            return None
        for resultitem in queryresult:
            qid = resultitem.get('grouping').replace(u'http://www.wikidata.org/entity/', u'')
            result[qid] = int(resultitem.get('count'))
        return result

    def get_property_info_no_grouping(self, property):
        """
        Get the usage counts for a property without a grouping

        :param property: Wikidata Pid of the property
        :return: (Ordered) dictionary with the counts per grouping
        """
        query = f("""
SELECT (COUNT(?entity) AS ?count) WHERE {{
    ?entity {self.selector_sparql} .
    MINUS {{ ?entity wdt:{self.grouping_property} _:b28. }}
    FILTER(EXISTS {{ ?entity p:{property} _:b29. }})
}}
GROUP BY ?grouping
ORDER BY DESC (?count)
LIMIT 10
""")
        return self._get_count_from_sparql(query)

    def get_totals_for_property(self, property):
        """
        Get the totals of entities with that property
        :param prop:  Wikidata Pid of the property.
        :return: number of games found
        """
        query = f("""
SELECT (COUNT(?item) as ?count) WHERE {{
  ?item {self.selector_sparql}
  FILTER EXISTS {{ ?item p:{property}[] }} .
}}

""")
        return self._get_count_from_sparql(query)

    def get_totals_no_grouping(self):
        query = f("""
SELECT (COUNT(?item) as ?count) WHERE {{
  ?item {self.selector_sparql}
  MINUS {{ ?item wdt:{self.grouping_property} _:b28. }}
}}
""")
        return self._get_count_from_sparql(query)

    def get_totals(self):
        query = f("""
SELECT (COUNT(?item) as ?count) WHERE {{
  ?item {self.selector_sparql}
}}
""")
        return self._get_count_from_sparql(query)

    @staticmethod
    def _get_count_from_sparql(query):
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)
        if not queryresult:
            return None
        return int(queryresult[0].get('count'))

    @staticmethod
    def _get_percentage(count, total):
        if not count:
            return 0
        return round(1.0 * count / max(total, 1) * 100, 2)

    def get_header(self):
        text = u'{| class="wikitable sortable"\n'
        colspan = 3 if self.higher_grouping else 2
        text += f('! colspan="{colspan}" |Top groupings (Minimum {self.grouping_threshold} items)\n')
        text += f('! colspan="{len(self.properties)}"|Top Properties (used at least {self.property_threshold} times per grouping)\n')  # noqa
        text += u'|-\n'

        if self.higher_grouping:
            text += u'! \n'

        text += u'! Name\n'
        text += u'! Count\n'
        for prop in self.properties:
            if self.properties.get(prop):
                label = f('[[Property:{prop}|{self.properties.get(prop)}]]')
            else:
                label = f('{{{{Property|{prop}}}}}')
            text += f('! data-sort-type="number"|{label}\n')
        return text

    def format_higher_grouping_text(self, higher_grouping_value):
        type_mapping = {
            "country": "{{Flag|%s}}" % higher_grouping_value,
            "string": "%s" % higher_grouping_value,
        }
        default = f('{{{{Q|{higher_grouping_value}}}}}')
        higher_grouping_text = type_mapping.get(self.higher_grouping_type, default)
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
        for prop in self.properties:
            propcount = self.get_property_info_no_grouping(prop)
            percentage = self._get_percentage(propcount, total_no_count)
            text += f('| {{{{{self.cell_template}|{percentage}|{propcount}}}}}\n')
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

        text += u'| {{Q|%s}}\n' % (grouping,)

        if self.grouping_link:
            group_item = pywikibot.ItemPage(self.repo, grouping)
            group_item.get()
            label = group_item.labels["en"]
            text += f('| [[{self.grouping_link}/{label}|{item_count}]] \n')
        else:
            text += f('| {item_count} \n')

        for prop in self.properties:
            try:
                propcount = self.property_data.get(prop).get(grouping)
            except AttributeError:
                propcount = 0
            if not propcount:
                propcount = 0
            percentage = self._get_percentage(propcount, item_count)
            text += f('| {{{{{self.cell_template}|{percentage}|{propcount}}}}}\n')
        return text

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
        for prop in self.properties:
            self.property_data[prop] = self.get_property_info(prop)

        text = self.get_header()

        for (grouping, item_count) in groupings_counts.items():
            higher_grouping = groupings_groupings.get(grouping)
            text += self.make_stats_for_one_grouping(grouping, item_count, higher_grouping)

        if self.stats_for_no_group:
            text += self.make_stats_for_no_group()

        # Get the totals
        total_items = self.get_totals()

        text += u'|- class="sortbottom"\n|'
        if self.higher_grouping:
            text += u"|\n|"

        text += f('\'\'\'Totals\'\'\' <small>(all items)<small>:\n| {total_items}\n')
        for prop in self.properties:
            totalprop = self.get_totals_for_property(property=prop)
            percentage = self._get_percentage(totalprop, total_items)
            text += f('| {{{{{self.cell_template}|{percentage}|{totalprop}}}}}\n')
        text += u'|}\n'
        return text


def main(*args):
    """
    Main function.
    """
    properties = collections.OrderedDict({
        'P21': None,
        'P19': None,
    })
    logging.info("Main function...")
    stats = PropertyStatistics(
        properties=properties,
        selector_sparql=u'wdt:P31 wd:Q41960',
        grouping_property=u'P551',
        stats_for_no_group=True,
        grouping_threshold=5
    )
    print(stats.retrieve_and_process_data())


if __name__ == "__main__":
    main()
