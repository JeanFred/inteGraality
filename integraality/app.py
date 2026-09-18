#!/usr/bin/python
"""Flask web application."""

import traceback

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from .dashboard_registry import CHRONIC_FAILURE_THRESHOLD, DashboardRegistry
from .pages_processor import (
    PagesProcessor,
    ProcessingException,
    TransientServerException,
)
from .sparql_utils import (
    QLeverSparqlQueryEngine,
    QueryException,
    SparqlEngineBuilder,
    add_prefixes_to_query,
)
from .sse import run_with_sse

app = Flask(__name__)

# Form token for the Main namespace, whose canonical name is the empty string
# which would otherwise collide with the "All / no filter" empty value.
MAIN_NAMESPACE_TOKEN = "(Main)"


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


@app.template_filter("iso_utc")
def iso_utc_filter(value):
    """Render a naive-UTC datetime as ISO-8601 with a Z suffix.

    DATETIME columns come back as naive datetimes (stored as UTC). The Z makes
    the value unambiguously UTC so the browser parses it correctly rather than
    as local time. Returns "" for None (never-run dashboards).
    """
    if value is None:
        return ""
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


@app.route("/healthz")
def healthcheck():
    return jsonify(status="healthy")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/browse")
def browse():
    # /browse was the original (published) name; /dashboards is now canonical.
    # Redirect so existing links/bookmarks keep working, carrying any filters.
    return redirect(url_for("dashboards", **request.args), code=301)


@app.route("/dashboards")
def dashboards():
    site_hostname = request.args.get("wiki")
    namespace = request.args.get("namespace")
    root_page = request.args.get("root")
    search = request.args.get("search")
    status = request.args.get("status")
    # The Main namespace has an empty canonical name, which collides with the
    # "no filter" sentinel. The form uses the token "(Main)" for it; translate
    # it back to the real empty-string canonical for the query.
    namespace_filter = namespace
    if namespace == MAIN_NAMESPACE_TOKEN:
        namespace_filter = ""
    # A namespace filter is active when the param is present (even if it
    # resolves to the empty-string Main namespace); "All" omits the param.
    namespace_active = namespace_filter is not None and (
        namespace_filter != "" or namespace == MAIN_NAMESPACE_TOKEN
    )
    is_filtered = any([site_hostname, namespace_active, root_page, search, status])
    with DashboardRegistry() as registry:
        dashboards = registry.list_dashboards(
            site_hostname=site_hostname,
            namespace_canonical=namespace_filter if namespace_active else None,
            root_page=root_page,
            search=search,
            status=status,
        )
        wikis = registry.list_wikis(
            namespace_canonical=namespace_filter if namespace_active else None,
        )
        namespaces = registry.list_namespaces(site_hostname=site_hostname)
        roots = registry.list_roots(
            site_hostname=site_hostname,
            namespace_canonical=namespace_filter if namespace_active else None,
        )
    return render_template(
        "dashboards.html",
        dashboards=dashboards,
        is_filtered=is_filtered,
        wikis=wikis,
        namespaces=namespaces,
        roots=roots,
        selected_wiki=site_hostname,
        selected_namespace=namespace,
        selected_root=root_page,
        search=search,
        selected_status=status,
        chronic_failure_threshold=CHRONIC_FAILURE_THRESHOLD,
        main_namespace_token=MAIN_NAMESPACE_TOKEN,
    )


@app.route("/runs")
def runs():
    site_hostname = request.args.get("wiki")
    with DashboardRegistry() as registry:
        run_list = registry.list_runs(site_hostname=site_hostname)
    return render_template(
        "runs.html",
        runs=run_list,
        selected_wiki=site_hostname,
    )


@app.route("/update")
def update():
    page_url = request.args.get("url")
    page_title = request.args.get("page")
    if "nostream" in request.args:
        return _update_sync(page_url, page_title)
    return render_template(
        "update_stream.html",
        page_title=page_title,
        page_url=page_url,
        qlever_ui_url=get_qlever_ui_url(page_url),
        sparql_prefixes=add_prefixes_to_query(""),
    )


def _update_sync(page_url, page_title):
    try:
        processor = PagesProcessor(page_url)
        elapsed_time = processor.process_one_page(page_title)
        return render_template(
            "update.html",
            page_title=page_title,
            page_url=page_url,
            elapsed_time=elapsed_time,
        )
    except QueryException as e:
        return (
            render_template(
                "update_query_error.html",
                page_title=page_title,
                page_url=page_url,
                error_message=e,
                query=e.query,
                qlever_ui_url=get_qlever_ui_url(page_url),
            ),
            422,
        )
    except TransientServerException as e:
        return (
            render_template(
                "update_transient_error.html",
                page_title=page_title,
                page_url=page_url,
                error_message=e,
            ),
            503,
        )
    except ProcessingException as e:
        return (
            render_template(
                "update_error.html",
                page_title=page_title,
                page_url=page_url,
                error_message=e,
            ),
            422,
        )
    except Exception as e:
        return (
            render_template(
                "update_unknown_error.html",
                page_title=page_title,
                page_url=page_url,
                error_message=traceback.format_exception(type(e), e, e.__traceback__),
            ),
            500,
        )


@app.route("/update/stream")
def update_stream():
    page_url = request.args.get("url")
    page_title = request.args.get("page")

    def do_update():
        processor = PagesProcessor(page_url)
        return processor.process_one_page(page_title)

    return Response(
        run_with_sse(do_update),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/queries")
def queries():
    page_url = request.args.get("url")
    page_title = request.args.get("page")
    column_key = request.args.get("column") or request.args.get("property")
    output_format = request.args.get("format")
    processor = None
    try:
        processor = PagesProcessor(page_url)
        stats = processor.make_stats_object_for_page_title(page_title)
        grouping = request.args.get("grouping")
        query_data = stats.get_queries_for_column(column_key, grouping)

        column = query_data["column"]
        positive_query = query_data["positive_query"]
        negative_query = query_data["negative_query"]
        formatted_predicate = query_data["formatted_predicate"]
        qlever_ui_url = get_qlever_ui_url(page_url)

        if output_format == "json":
            return jsonify(
                page_title=page_title,
                page_url=page_url,
                column=column.get_key(),
                grouping=grouping,
                formatted_predicate=formatted_predicate,
                positive_query=positive_query,
                negative_query=negative_query,
                qlever_ui_url=qlever_ui_url,
            )

        return render_template(
            "queries.html",
            page_title=page_title,
            page_url=page_url,
            column=column,
            grouping=grouping,
            formatted_predicate=formatted_predicate,
            positive_query=positive_query,
            negative_query=negative_query,
            qlever_ui_url=qlever_ui_url,
        )
    except TransientServerException as e:
        if output_format == "json":
            return jsonify(error=str(e)), 503
        return (
            render_template(
                "queries_transient_error.html",
                page_title=page_title,
                page_url=page_url,
                error_message=e,
            ),
            503,
        )
    except ProcessingException as e:
        if output_format == "json":
            return jsonify(error=str(e)), 422
        return (
            render_template(
                "queries_error.html",
                page_title=page_title,
                page_url=page_url,
                error_message=e,
            ),
            422,
        )
    except Exception as e:
        if output_format == "json":
            return jsonify(error=str(e)), 500
        return (
            render_template(
                "queries_unknown_error.html",
                page_title=page_title,
                page_url=page_url,
                error_message=traceback.format_exception(type(e), e, e.__traceback__),
            ),
            500,
        )


@app.errorhandler(404)
def page_not_found(error):
    return render_template("page_not_found.html", title="Page not found"), 404


if __name__ == "__main__":
    app.run()
