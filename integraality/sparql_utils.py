#!/usr/bin/python
# -*- coding: utf-8 -*-

import pywikibot.data.sparql


class QueryException(Exception):
    def __init__(self, message, query):
        super().__init__(message)
        self.query = query


UNKNOWN_VALUE_PREFIX = "http://www.wikidata.org/.well-known/genid/"


class SparqlQueryEngine:
    pass


class WdqsSparqlQueryEngine(SparqlQueryEngine):
    def __init__(self):
        self.sq = pywikibot.data.sparql.SparqlQuery()

    def select(self, query):
        return self.sq.select(query)
