#!/usr/bin/python
# -*- coding: utf-8 -*-


class QueryException(Exception):
    def __init__(self, message, query):
        super().__init__(message)
        self.query = query


UNKNOWN_VALUE_PREFIX = "http://www.wikidata.org/.well-known/genid/"
