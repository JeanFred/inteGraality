#!/usr/bin/python
# -*- coding: utf-8 -*-
"""SPARQL engine abstraction (WDQS and QLever)."""

import pywikibot
import pywikibot.data.sparql
import requests
from rdflib.plugins.sparql.processor import prepareQuery

from .error_category import ErrorCategory


class QueryException(Exception):
    # Neutral default: a query failed for a reason we haven't classified.
    # Subclasses below assert a specific, honest cause.
    error_category = ErrorCategory.ERROR

    def __init__(self, message, query):
        super().__init__(message)
        self.query = query


class QuerySyntaxException(QueryException):
    """A SPARQL query failed local syntax validation before being sent.

    The user's query is malformed -- they must fix it."""

    error_category = ErrorCategory.QUERY


class QueryTimeoutException(QueryException):
    """An endpoint took too long. Could be a transient slow moment, a
    genuinely too-expensive query, or a subtly broken one (e.g. an accidental
    cartesian product) -- indistinguishable from the timeout alone, so its own
    category rather than forced into query/transient."""

    error_category = ErrorCategory.TIMEOUT


class BackendUnavailableException(QueryException):
    """The SPARQL endpoint was unreachable/erroring (not the user's query).
    Retry later."""

    error_category = ErrorCategory.TRANSIENT


UNKNOWN_VALUE_PREFIX = "http://www.wikidata.org/.well-known/genid/"


class UnsupportedSparqlEngineException(Exception):
    pass


class SparqlEngineBuilder:
    @staticmethod
    def make(sparql_endpoint=None, site_url=None):
        """Create appropriate SPARQL engine based on endpoint and site URL.

        If site_url points to Wikimedia Commons, force the QLever
        wikimedia-commons endpoint regardless of sparql_endpoint.
        """
        if site_url and "commons.wikimedia.org" in site_url:
            return QLeverSparqlQueryEngine(
                endpoint="https://qlever.dev/api/wikimedia-commons"
            )
        if sparql_endpoint:
            if "qlever" in sparql_endpoint.lower():
                return QLeverSparqlQueryEngine()
            elif "query.wikidata.org" in sparql_endpoint.lower():
                return WdqsSparqlQueryEngine()
            else:
                raise UnsupportedSparqlEngineException(
                    f"The {sparql_endpoint} URL provided is not supported"
                )
        return WdqsSparqlQueryEngine()


class SparqlQueryEngine:
    def select(self, query):
        """Run a SPARQL SELECT query.

        Template method: subclasses implement _do_select. Kept as a
        single entry point so cross-cutting concerns (e.g. validation)
        live in one place rather than in every engine.
        """
        validate_query_syntax(query)
        return self._do_select(query)

    def _do_select(self, query):
        raise NotImplementedError


class WdqsSparqlQueryEngine(SparqlQueryEngine):
    name = "Wikidata Query Service"

    def __init__(self):
        self.sq = pywikibot.data.sparql.SparqlQuery(
            endpoint="https://query.wikidata.org/sparql",
            entity_url="http://www.wikidata.org/entity/",
        )

    def _do_select(self, query):
        try:
            result = self.sq.select(query)
        except (pywikibot.exceptions.ApiTimeoutError, pywikibot.exceptions.ServerError):
            raise QueryTimeoutException(
                "The Wikidata Query Service timed out when running a SPARQL query. "
                "You might be trying to do something too expensive.",
                query=query,
            )

        if result is None:
            # None (not []) means a malformed/error body from WDQS; treat as transient.
            raise BackendUnavailableException(
                "The Wikidata Query Service returned no result "
                "(it may be overloaded or timing out); please try again later.",
                query=query,
            )

        return result


STANDARD_PREFIXES = [
    "PREFIX wd: <http://www.wikidata.org/entity/>",
    "PREFIX wdt: <http://www.wikidata.org/prop/direct/>",
    "PREFIX p: <http://www.wikidata.org/prop/>",
    "PREFIX ps: <http://www.wikidata.org/prop/statement/>",
    "PREFIX pq: <http://www.wikidata.org/prop/qualifier/>",
    "PREFIX pr: <http://www.wikidata.org/prop/reference/>",
    "PREFIX prov: <http://www.w3.org/ns/prov#>",
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>",
    "PREFIX schema: <http://schema.org/>",
    "PREFIX bd: <http://www.bigdata.com/rdf#>",
    "PREFIX wikibase: <http://wikiba.se/ontology#>",
    "PREFIX wdno: <http://www.wikidata.org/prop/novalue/>",
]


def add_prefixes_to_query(query):
    """Prepend standard Wikidata prefixes so QLever can resolve them.

    Also reused by validate_query_syntax so the local parser resolves
    the same prefixes WDQS provides implicitly.
    """
    return "\n".join(STANDARD_PREFIXES) + "\n" + query


def validate_query_syntax(query):
    """Check SPARQL syntax locally before sending to an endpoint.

    Prepends the standard prefixes so queries relying on them (as WDQS
    does implicitly) don't fail on undefined prefixes. Raises
    QuerySyntaxException on a parse error. Note: rdflib parses standard
    SPARQL 1.1, so Blazegraph-specific extensions (e.g. hint:) are
    rejected — acceptable as WDQS moves off Blazegraph.
    """
    try:
        prepareQuery(add_prefixes_to_query(query))
    except Exception as e:
        raise QuerySyntaxException(
            "The SPARQL query could not be parsed. It may contain a syntax "
            "error, or use Blazegraph-specific extensions (such as hint:) "
            "that WDQS is phasing out and are no longer supported. "
            f"Parser error: {e}",
            query=query,
        ) from e


class QLeverSparqlQueryEngine(SparqlQueryEngine):
    name = "QLever"

    def __init__(self, endpoint="https://qlever.dev/api/wikidata"):
        self.endpoint = endpoint

    @property
    def ui_url(self):
        return self.endpoint.replace("/api/", "/") + "/"

    def _do_select(self, query):
        try:
            query = add_prefixes_to_query(query)

            params = {"query": query}
            response = requests.get(self.endpoint, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            return self._transform_response(data)

        except requests.exceptions.HTTPError as e:
            raise BackendUnavailableException(
                "QLever is not available, please try again later.",
                query=query,
            ) from e

        except requests.exceptions.Timeout:
            raise QueryTimeoutException(
                "QLever timed out when running a SPARQL query. "
                "You might be trying to do something too expensive.",
                query=query,
            )

        except requests.exceptions.RequestException as e:
            # Connection errors, DNS failures, etc. -- the backend is
            # unreachable, not the user's query.
            raise BackendUnavailableException(
                "QLever is not available, please try again later.",
                query=query,
            ) from e

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


def expand_select_vars(vars_list):
    """Expand a list of SPARQL variables into a SELECT clause with labels.

    ['?entity', '?value'] → '?entity ?entityLabel ?value ?valueLabel'
    """
    return " ".join(f"{var} {var}Label" for var in vars_list)


def get_labels_for_select_vars(vars_list):
    """Derive label-resolution SPARQL from a list of SPARQL variables.

    For each variable, generates OPTIONAL/BIND blocks that resolve
    rdfs:label into a corresponding ?varLabel variable.
    """
    lines = []
    for var in vars_list:
        lines.extend(get_label_for_variable(var, f"{var}Label"))
    return "\n".join(lines) + "\n"


def get_label_for_variable(subject_variable, output_variable, lang="en"):
    """Generate SPARQL fragment to get label with fallback from given language to 'mul'."""
    variable_base = subject_variable.lstrip("?")
    mul_label = f"?{variable_base}labelMUL"
    lines = [
        "  OPTIONAL {{",
        f"    {subject_variable} rdfs:label {mul_label}.",
        f"    FILTER(lang({mul_label})='mul')",
        "  }}.",
    ]
    if lang == "mul":
        lines.append(f"  BIND({mul_label} AS {output_variable}).")
    else:
        lang_upper = lang.upper()
        lang_label = f"?{variable_base}label{lang_upper}"
        lines.extend(
            [
                "  OPTIONAL {{",
                f"    {subject_variable} rdfs:label {lang_label}.",
                f"    FILTER(lang({lang_label})='{lang}')",
                "  }}.",
                f"  BIND(COALESCE({lang_label}, {mul_label}) AS {output_variable}).",
            ]
        )
    return lines
