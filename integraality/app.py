#!/usr/bin/python
# -*- coding: utf-8  -*-

import traceback

from flask import Flask, jsonify, render_template, request

from pages_processor import (
    PagesProcessor,
    ProcessingException,
    TransientServerException,
)
from sparql_utils import (
    QLeverSparqlQueryEngine,
    QueryException,
    SparqlEngineBuilder,
    add_prefixes_to_query,
)

app = Flask(__name__)
app.debug = True


def get_qlever_ui_url(page_url):
    """Return the QLever UI URL for the given wiki page URL."""
    engine = SparqlEngineBuilder.make(site_url=page_url)
    if isinstance(engine, QLeverSparqlQueryEngine):
        return engine.ui_url
    return "https://qlever.dev/wikidata/"


@app.template_filter("add_prefixes")
def add_prefixes_filter(query):
    """Jinja filter to add prefixes to SPARQL queries for QLever."""
    return add_prefixes_to_query(query)


@app.route("/healthz")
def healthcheck():
    return jsonify(status="healthy")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/update")
def update():
    page_url = request.args.get("url")
    page_title = request.args.get("page")
    processor = PagesProcessor(page_url)
    try:
        elapsed_time = processor.process_one_page(page_title)
        return render_template(
            "update.html",
            page_title=page_title,
            page_url=page_url,
            elapsed_time=elapsed_time,
        )
    except QueryException as e:
        return render_template(
            "update_query_error.html",
            page_title=page_title,
            page_url=page_url,
            error_message=e,
            query=e.query,
            qlever_ui_url=get_qlever_ui_url(page_url),
        )
    except TransientServerException as e:
        return render_template(
            "update_transient_error.html",
            page_title=page_title,
            page_url=page_url,
            error_message=e,
        )
    except ProcessingException as e:
        return render_template(
            "update_error.html",
            page_title=page_title,
            page_url=page_url,
            error_message=e,
        )
    except Exception as e:
        return render_template(
            "update_unknown_error.html",
            page_title=page_title,
            page_url=page_url,
            error_message=traceback.format_exception(type(e), e, e.__traceback__),
        )


@app.route("/queries")
def queries():
    page_url = request.args.get("url")
    page_title = request.args.get("page")
    column_key = request.args.get("column") or request.args.get("property")
    processor = PagesProcessor(page_url)
    try:
        stats = processor.make_stats_object_for_page_title(page_title)
        grouping = request.args.get("grouping")
        column = stats.columns.get(column_key)
        positive_query = stats.get_query_for_items_for_property_positive(
            column, grouping
        )
        negative_query = stats.get_query_for_items_for_property_negative(
            column, grouping
        )
        formatted_predicate = stats.grouping_configuration.format_predicate_html()
        qlever_ui_url = get_qlever_ui_url(page_url)
        return render_template(
            "queries.html",
            page_title=page_title,
            page_url=page_url,
            column=column,
            grouping=request.args.get("grouping"),
            formatted_predicate=formatted_predicate,
            positive_query=positive_query,
            negative_query=negative_query,
            qlever_ui_url=qlever_ui_url,
        )
    except ProcessingException as e:
        return render_template(
            "queries_error.html",
            page_title=page_title,
            page_url=page_url,
            error_message=e,
        )
    except Exception as e:
        return render_template(
            "queries_unknown_error.html",
            page_title=page_title,
            page_url=page_url,
            error_message=traceback.format_exception(type(e), e, e.__traceback__),
        )


@app.errorhandler(404)
def page_not_found(error):
    return render_template("page_not_found.html", title="Page not found"), 404


if __name__ == "__main__":
    app.run()
