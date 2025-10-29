#!/usr/bin/python
# -*- coding: utf-8 -*-

import pywikibot
import pywikibot.data.sparql

import requests


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
        try:
            return self.sq.select(query)
        except (pywikibot.exceptions.TimeoutError, pywikibot.exceptions.ServerError):
            raise QueryException(
                "The Wikidata Query Service timed out when running a SPARQL query."
                "You might be trying to do something too expensive.",
                query=query,
            )


def add_prefixes_to_query(query):
    """Add standard Wikidata prefixes to a SPARQL query for QLever."""
    prefixes = [
        "PREFIX wd: <http://www.wikidata.org/entity/>",
        "PREFIX wdt: <http://www.wikidata.org/prop/direct/>",
        "PREFIX p: <http://www.wikidata.org/prop/>",
        "PREFIX ps: <http://www.wikidata.org/prop/statement/>",
        "PREFIX pq: <http://www.wikidata.org/prop/qualifier/>",
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>",
        "PREFIX schema: <http://schema.org/>",
        "PREFIX bd: <http://www.bigdata.com/rdf#>",
        "PREFIX wikibase: <http://wikiba.se/ontology#>",
        "PREFIX wdno: <http://www.wikidata.org/prop/novalue/>",
    ]
    return "\n".join(prefixes) + "\n" + query


class QLeverSparqlQueryEngine(SparqlQueryEngine):
    def __init__(self):
        self.endpoint = "https://qlever.dev/api/wikidata"

    def select(self, query):
        try:
            query = add_prefixes_to_query(query)

            params = {"query": query}
            response = requests.get(self.endpoint, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            return self._transform_response(data)

        except requests.exceptions.HTTPError as e:
            raise QueryException(
                "QLever is not available, please try again later.",
                query=query,
            ) from e

        except (requests.exceptions.Timeout, requests.exceptions.RequestException):
            raise QueryException(
                "QLever timed out when running a SPARQL query."
                "You might be trying to do something too expensive.",
                query=query,
            )

    def _transform_response(self, data):
        """Transform QLever response to expected format."""
        if "results" in data and "bindings" in data["results"]:
            result = []
            for binding in data["results"]["bindings"]:
                row = {}
                for var, value in binding.items():
                    row[var] = value["value"]
                result.append(row)
            return result
        return []
