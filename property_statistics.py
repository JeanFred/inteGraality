#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Calculate and generate statistics

"""
import collections
import logging

import pywikibot
import pywikibot.data.sparql


class PropertyStatistics:
    """
    Generate statitics

    """
    def __init__(self, selector_sparql, properties, grouping_property, higher_grouping=None, higher_grouping_type=None, no_group_stats=False, grouping_link=None, grouping_threshold=20, property_threshold=10):  # noqa
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
        self.no_group_stats = no_group_stats
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
            query = f"""
SELECT ?grouping (SAMPLE(?_higher_grouping) as ?higher_grouping) (COUNT(?entity) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?grouping .
  OPTIONAL {{ ?grouping {self.higher_grouping} ?_higher_grouping }}.
}} GROUP BY ?grouping ?higher_grouping
HAVING (?count > {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 10
"""
        else:
            query = f"""
SELECT ?grouping (COUNT(?entity) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?grouping .
}} GROUP BY ?grouping
HAVING (?count > {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 10
"""
        print(query)
        grouping_counts = collections.OrderedDict()

        grouping_groupings = collections.OrderedDict()

        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)

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
        query = f"""
SELECT ?grouping (COUNT(?entity) as ?count) WHERE {{
  ?entity {self.selector_sparql} .
  ?entity wdt:{self.grouping_property} ?grouping .
  FILTER EXISTS {{ ?entity p:{property} [] }} .
}} GROUP BY ?grouping
HAVING (?count > {self.grouping_threshold})
ORDER BY DESC(?count)
LIMIT 10
"""
        result = collections.OrderedDict()
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)
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
        query = f"""
SELECT (COUNT(?entity) AS ?count) WHERE {{
    ?entity {self.selector_sparql} .
    MINUS {{ ?entity wdt:{self.grouping_property} _:b28. }}
    FILTER(EXISTS {{ ?entity p:{property} _:b29. }})
}}
GROUP BY ?grouping
ORDER BY DESC (?count)
LIMIT 10
"""
        return self._get_count_from_sparql(query)

    def get_totals_for_property(self, property):
        """
        Get the totals of entities with that property
        :param prop:  Wikidata Pid of the property.
        :return: number of games found
        """
        query = f"""
SELECT (COUNT(?item) as ?count) WHERE {{
  ?item {self.selector_sparql}
  FILTER EXISTS {{ ?item p:{property}[] }} .
}}
"""
        return self._get_count_from_sparql(query)

    def get_totals_no_grouping(self):
        query = f"""
SELECT (COUNT(?item) as ?count) WHERE {{
  ?item {self.selector_sparql}
  MINUS {{ ?item wdt:{self.grouping_property} _:b28. }}
}}
"""
        return self._get_count_from_sparql(query)

    def get_totals(self):
        query = f"""
SELECT (COUNT(?item) as ?count) WHERE {{
  ?item {self.selector_sparql}
}}
"""
        print(query)
        return self._get_count_from_sparql(query)

    @staticmethod
    def _get_count_from_sparql(query):
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)
        for resultitem in queryresult:
            # Just one result, return that right away
            return int(resultitem.get('count'))

    @staticmethod
    def _get_percentage(count, total):
        if not count:
            return 0
        return round(1.0 * count / max(total, 1) * 100, 2)

    def get_header(self):
        text = u'{| class="wikitable sortable"\n'
        colspan = 3 if self.higher_grouping else 2
        text += f'! colspan="{colspan}" |Top groupings (Minimum {self.grouping_threshold} items)\n'
        text += f'! colspan="{len(self.properties)}"|Top Properties (used at least {self.property_threshold} times per grouping)\n'  # noqa
        text += u'|-\n'

        if self.higher_grouping:
            text += u'! \n'

        text += u'! Name\n'
        text += u'! Count\n'
        for prop in self.properties:
            if self.properties.get(prop):
                label = f'[[Property:{prop}|{self.properties.get(prop)}]]'
            else:
                label = f'{{{{Property|{prop}}}}}'
            text += f'! data-sort-type="number"|{label}\n'
        return text

    def retrieve_and_process_data(self):
        """
        Query the data, output wikitext
        """
        logging.info("Retrieving grouping information...")
        (groupings_counts, groupings_groupings) = self.get_grouping_information()

        logging.info(f"Grouping retrieved: {len(groupings_counts)}")
        for prop in self.properties:
            self.property_data[prop] = self.get_property_info(prop)

        text = self.get_header()

        for grouping in groupings_counts:
            item_count = groupings_counts.get(grouping)
            item = pywikibot.ItemPage(self.repo, grouping)
            item.get()

            text += u'|-\n'

            if self.higher_grouping:
                higher_grouping_value = groupings_groupings.get(grouping)

                if higher_grouping_value:
                    type_mapping = {
                        "country": "{{Flag|%s}}" % higher_grouping_value,
                    }
                    higher_grouping_text = type_mapping.get(self.higher_grouping_type, f'{{{{Q|{higher_grouping_value}}}}}')  # noqa
                    text += f'| data-sort-value="{higher_grouping_value}"| {higher_grouping_text}\n'
                else:
                    text += u'|\n'

            text += u'| {{Q|%s}}\n' % (grouping,)

            if self.grouping_link:
                text += f'| [[{self.grouping_link}/{item.labels["en"]}|{item_count}]]'
            else:
                text += f'| {item_count} \n'

            for prop in self.properties:
                propcount = self.property_data.get(prop).get(grouping)
                if not propcount:
                    propcount = 0
                percentage = self._get_percentage(propcount, item_count)
                text += f'| {{{{{self.cell_template}|{percentage}|{propcount}}}}}\n'

        if self.no_group_stats:
            text += u'|-\n'

            if self.higher_grouping:
                text += u'|\n'

            total_no_count = self.get_totals_no_grouping()
            text += u'| No grouping \n'
            text += f'| {total_no_count} \n'
            for prop in self.properties:
                propcount = self.get_property_info_no_grouping(prop)
                percentage = self._get_percentage(propcount, total_no_count)
                text += f'| {{{{{self.cell_template}|{percentage}|{propcount}}}}}\n'

        # Get the totals
        total_items = self.get_totals()

        text += u'|- class="sortbottom"\n|'
        if self.higher_grouping:
            text += u"|\n|"

        text += f'\'\'\'Totals\'\'\' <small>(all items)<small>:\n| {total_items}\n'
        for prop in self.properties:
            totalprop = self.get_totals_for_property(property=prop)
            percentage = self._get_percentage(totalprop, total_items)
            text += f'| {{{{{self.cell_template}|{percentage}|{totalprop}}}}}\n'
        text += u'|}\n'
        return text

    def run(self, target_page_title):
        wikitext = self.retrieve_and_process_data()
        page = pywikibot.Page(self.repo, title=target_page_title)
        summary = u'Property usage stats'
        print(wikitext)
        page.put(wikitext, summary)


def main(*args):
    """
    Main function.
    """
    properties = collections.OrderedDict({
        # Core properties
        # 'P136': u'genre',
        # 'P178': u'developer',
        # 'P123': u'publisher',
        # 'P495': u'country',
        # 'P577': u'publication date',

        # # Gameplay properties
        # 'P404': None,
        # 'P437': None,

        # # # Staff properties
        # 'P57': u'director',
        # 'P287': u'designer',
        # 'P86': u'composer',
        # 'P162': u'producer',

        # # # Setting
        # 'P1434': u'universe',
        # 'P840': u'narrative location',
        # 'P2408': u'narrative period',
    })

    stats = PropertyStatistics(
        properties=properties,
        selector_sparql=u'wdt:P31/wdt:P279* wd:Q7889 ',
        grouping_property=u'P400',
        no_group_stats=True,
        grouping_threshold=1
    )
    stats.run(u'Wikidata:WikiProject Video games/Statistics/Platform',)


if __name__ == "__main__":
    main()
