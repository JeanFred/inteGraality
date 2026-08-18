"""Functional tests: run SPARQL queries extracted from unit tests against live endpoints.

Uses AST introspection to find all triple-quoted strings assigned to
`query` or `expected` variables in the unit test modules, keeps only those
starting with SELECT, and fires them at WDQS and QLever.

Run with:
    uv run pytest integraality/tests/test_sparql_functional.py -m functional -k qlever -s -q --tb=line

Skipped by default (see pyproject.toml addopts).
"""

import ast
import os
import re
import sys
import time
import warnings

import pytest

from ..sparql_utils import (
    QLeverSparqlQueryEngine,
    QueryException,
    WdqsSparqlQueryEngine,
)

pytestmark = pytest.mark.functional

# Minimum seconds between requests to the same endpoint
RATE_LIMIT_SECONDS = 4
_last_request_time = {}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_limit(query, limit=1):
    """Replace existing LIMIT or inject a small one to be kind to endpoints."""
    query = re.sub(r"LIMIT\s+\d+", f"LIMIT {limit}", query, flags=re.IGNORECASE)
    if "LIMIT" not in query.upper():
        return query.rstrip() + f"\nLIMIT {limit}\n"
    return query


_TIMEOUT = object()  # sentinel for timed-out queries


def _throttled_select(engine, query):
    """Select with rate limiting."""
    elapsed = time.monotonic() - _last_request_time.get(engine.name, 0)
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)

    try:
        _last_request_time[engine.name] = time.monotonic()
        result = engine.select(_add_limit(query))
        if result is None:
            return _TIMEOUT
        return result
    except QueryException as e:
        if "timed out" in str(e).lower() or "not available" in str(e).lower():
            return _TIMEOUT
        raise


# ---------------------------------------------------------------------------
# AST-based query extraction
# ---------------------------------------------------------------------------

TEST_MODULES = [
    "test_property_statistics.py",
    "test_column.py",
]


def _extract_queries_from_file(filepath):
    """Parse a test file's AST and yield (class_name, method, query) tuples."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    def _extract_from_function(func_node, class_name=None):
        for child in ast.walk(func_node):
            if not isinstance(child, ast.Assign):
                continue
            for target in child.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id not in ("query", "expected"):
                    continue
                value = child.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    text = value.value.strip()
                    if text.upper().startswith("SELECT"):
                        yield (class_name or "", func_node.name, text)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield from _extract_from_function(child, class_name=node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield from _extract_from_function(node)


def _collect_all_queries():
    """Collect all unique SPARQL queries as (class_name, method, test_id, query) tuples."""
    tests_dir = os.path.dirname(__file__)
    queries = []
    seen = set()
    for module in TEST_MODULES:
        filename = os.path.basename(module).removesuffix(".py")
        filepath = os.path.join(tests_dir, module)
        for class_name, method, query in _extract_queries_from_file(filepath):
            if query not in seen:
                seen.add(query)
                test_id = (
                    f"{filename}/{class_name}/{method}"
                    if class_name
                    else f"{filename}/{method}"
                )
                queries.append((class_name, method, test_id, query))
    return queries


ALL_QUERIES = _collect_all_queries()

# Queries that are syntactically valid but return no results by design.
# Uses test_id strings (file/Class/method) for matching.
SYNTAX_ONLY = {
    "test_property_statistics/GetQueryForItemsForPropertyPositive/test_get_query_for_items_for_property_positive_unknown_value_grouping",
    "test_property_statistics/GetQueryForItemsForPropertyNegative/test_get_query_for_items_for_property_negative_unknown_value_grouping",
    "test_column/TestPropertyColumnWithQualifierAndVariableValue/test_get_info_query",
}


def _is_syntax_only(test_id):
    """Check if a test_id matches a SYNTAX_ONLY entry."""
    return test_id in SYNTAX_ONLY


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

# Track results for summary.
# Note: module-level mutable state — assumes single-process test execution (no xdist).
_results = {}  # {engine_name: [(class_name, method, status)]}
_last_class = {}  # {engine_name: class_name} — for grouping headers


def _format_row_compact(row):
    """Format a result row compactly (truncated values, no long URIs)."""
    parts = []
    for key, val in row.items():
        val = str(val).replace("http://www.wikidata.org/entity/", "")
        if len(val) > 30:
            val = val[:27] + "…"
        parts.append(f"{key}={val}")
    result = ", ".join(parts)
    if len(result) > 80:
        result = result[:77] + "…"
    return result


def _print_result(engine_name, class_name, method, status, detail=""):
    """Print a single result line with class grouping."""
    # Print class header when group changes
    if _last_class.get(engine_name) != class_name:
        _last_class[engine_name] = class_name
        print(f"\n  {engine_name} ─ {class_name}", file=sys.stderr)

    # Status icon
    icons = {"ok": "✓", "timeout": "⏱", "syntax": "~", "fail": "✗"}
    icon = icons.get(status, "?")

    if detail:
        print(f"    {icon} {method:<50} → {detail}", file=sys.stderr)
    else:
        print(f"    {icon} {method}", file=sys.stderr)

    # Record for summary
    _results.setdefault(engine_name, []).append((class_name, method, status))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qlever_engine():
    return QLeverSparqlQueryEngine()


@pytest.fixture(scope="module")
def wdqs_engine():
    return WdqsSparqlQueryEngine()


def _run_query(engine_name, engine, class_name, method, test_id, query):
    """Run a query and print/record the result."""
    result = _throttled_select(engine, query)
    if result is _TIMEOUT:
        warnings.warn(f"{engine_name} timeout: {test_id}")
        _print_result(engine_name, class_name, method, "timeout", "timeout")
        return
    if result:
        _print_result(
            engine_name, class_name, method, "ok", _format_row_compact(result[0])
        )
    elif _is_syntax_only(test_id):
        _print_result(
            engine_name, class_name, method, "syntax", "no results (syntax-only)"
        )
    else:
        _print_result(engine_name, class_name, method, "fail", "no results")
    if _is_syntax_only(test_id):
        assert result is not None, f"Query failed to execute for {test_id}\n\n{query}"
    else:
        assert len(result) > 0, f"Query returned no results for {test_id}\n\n{query}"


@pytest.mark.parametrize(
    "class_name,method,test_id,query",
    ALL_QUERIES,
    ids=[q[2] for q in ALL_QUERIES],
)
def test_query_on_qlever(class_name, method, test_id, query, qlever_engine):
    """Each SPARQL query from unit tests should execute on QLever."""
    _run_query("QLever", qlever_engine, class_name, method, test_id, query)


@pytest.mark.parametrize(
    "class_name,method,test_id,query",
    ALL_QUERIES,
    ids=[q[2] for q in ALL_QUERIES],
)
def test_query_on_wdqs(class_name, method, test_id, query, wdqs_engine):
    """Each SPARQL query from unit tests should execute on WDQS."""
    _run_query("WDQS", wdqs_engine, class_name, method, test_id, query)


# ---------------------------------------------------------------------------
# Summary (printed after all tests in this module complete)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="module")
def _print_summary(request):
    """Print a summary table after all functional tests in this module complete."""
    yield
    if not _results:
        return

    print("\n", file=sys.stderr)
    print("  ═══ Functional test summary ═══", file=sys.stderr)
    print(file=sys.stderr)

    for engine_name in sorted(_results):
        results = _results[engine_name]
        ok = sum(1 for _, _, s in results if s == "ok")
        timeouts = [(c, m) for c, m, s in results if s == "timeout"]
        syntax = sum(1 for _, _, s in results if s == "syntax")
        fails = [(c, m) for c, m, s in results if s == "fail"]
        total = len(results)

        parts = [f"{ok}/{total} ✓"]
        if syntax:
            parts.append(f"{syntax} ~")
        if timeouts:
            parts.append(f"{len(timeouts)} ⏱")
        if fails:
            parts.append(f"{len(fails)} ✗")

        print(f"  {engine_name:<8} {', '.join(parts)}", file=sys.stderr)

    for engine_name in sorted(_results):
        results = _results[engine_name]
        timeouts = [(c, m) for c, m, s in results if s == "timeout"]
        if timeouts:
            print(f"\n  Timeouts ({engine_name}):", file=sys.stderr)
            for cls, method in timeouts:
                print(f"    {cls}/{method}", file=sys.stderr)

    for engine_name in sorted(_results):
        results = _results[engine_name]
        fails = [(c, m) for c, m, s in results if s == "fail"]
        if fails:
            print(f"\n  Failures ({engine_name}):", file=sys.stderr)
            for cls, method in fails:
                print(f"    {cls}/{method}", file=sys.stderr)

    print(file=sys.stderr)
