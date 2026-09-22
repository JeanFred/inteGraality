import json
import unittest
from datetime import datetime
from unittest.mock import patch

from .. import column
from ..app import RUNS_TABLE_CAP, app
from ..dashboard_registry import DashboardRegistry
from ..pages_processor import ProcessingException, TransientServerException
from ..sparql_utils import QueryException, QueryTimeoutException


class AppTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.app = app.test_client()


class IsoUtcFilterTest(unittest.TestCase):
    def test_formats_naive_datetime_with_z(self):
        from ..app import iso_utc_filter

        self.assertEqual(
            iso_utc_filter(datetime(2026, 9, 11, 18, 54, 17)),
            "2026-09-11T18:54:17Z",
        )

    def test_none_is_empty_string(self):
        from ..app import iso_utc_filter

        self.assertEqual(iso_utc_filter(None), "")


class BasicTests(AppTests):
    def test_index_page(self):
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("<h1>inteGraality</h1>", response.get_data(as_text=True))

    def test_healthz(self):
        response = self.app.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "healthy"})

    def test_404_page(self):
        response = self.app.get("/unexisting_page")
        self.assertEqual(response.status_code, 404)
        self.assertIn("This page does not exist.", response.get_data(as_text=True))


class DashboardsTests(AppTests):
    def setUp(self):
        super().setUp()
        patcher = patch("integraality.app.DashboardRegistry", autospec=True)
        self.mock_registry_cls = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_registry = self.mock_registry_cls.return_value.__enter__.return_value
        # Sensible defaults; individual tests override list_dashboards.
        self.mock_registry.list_dashboards.return_value = []
        self.mock_registry.list_wikis.return_value = []
        self.mock_registry.list_namespaces.return_value = []
        self.mock_registry.list_roots.return_value = []

    def _dashboard(
        self,
        title,
        root,
        latest_status=None,
        latest_finished_at=None,
        last_success_at=None,
        recent_statuses=None,
        failures_since_success=0,
    ):
        return {
            "page_url": "https://www.wikidata.org/wiki/{}".format(
                title.replace(" ", "_")
            ),
            "page_title": title,
            "site_hostname": "www.wikidata.org",
            "site_name": "Wikidata",
            "namespace_canonical": "Project",
            "namespace_localized": "Wikidata",
            "root_page": root,
            "latest_status": latest_status,
            "latest_finished_at": latest_finished_at,
            "latest_duration_ms": None,
            "last_success_at": last_success_at,
            "recent_statuses": recent_statuses,
            "failures_since_success": failures_since_success,
        }

    def test_browse_with_dashboards(self):
        self.mock_registry.list_dashboards.return_value = [
            self._dashboard("My Dashboard", "My Dashboard"),
            self._dashboard("Other", "Other"),
        ]
        response = self.app.get("/dashboards")
        self.assertEqual(response.status_code, 200)
        contents = response.get_data(as_text=True)
        self.assertIn("My Dashboard", contents)
        self.assertIn("Other", contents)
        self.assertIn("2</strong> dashboards registered.", contents)

    def test_browse_renders_run_history_strip(self):
        self.mock_registry.list_dashboards.return_value = [
            self._dashboard(
                "Flaky", "Flaky", latest_status="OK", recent_statuses="OK,FAIL,OK"
            ),
            self._dashboard("Fresh", "Fresh"),  # never run, no strip
        ]
        contents = self.app.get("/dashboards").get_data(as_text=True)
        self.assertIn("run-tick-ok", contents)
        self.assertIn("run-tick-fail", contents)
        self.assertIn("never run", contents)  # the strip-less dashboard

    def test_browse_renders_null_edit_tick(self):
        """A NULL token (OK run, no revision) renders the hollow-green tick
        with a 'no change' tooltip, distinct from a plain OK tick."""
        self.mock_registry.list_dashboards.return_value = [
            self._dashboard(
                "Stable", "Stable", latest_status="OK", recent_statuses="OK,NULL,NULL"
            ),
        ]
        contents = self.app.get("/dashboards").get_data(as_text=True)
        self.assertIn("run-tick-null", contents)
        self.assertIn("OK — no change (null edit)", contents)

    def test_browse_tints_transient_vs_chronic_failures(self):
        self.mock_registry.list_dashboards.return_value = [
            # 1 failure since last success -> transient -> amber (warning).
            self._dashboard(
                "JustBroke",
                "JustBroke",
                latest_status="FAIL",
                failures_since_success=1,
                recent_statuses="OK,FAIL",
            ),
            # >= threshold consecutive failures -> chronic -> red (danger).
            self._dashboard(
                "LongBroken",
                "LongBroken",
                latest_status="FAIL",
                failures_since_success=9,
                recent_statuses="FAIL,FAIL,FAIL",
            ),
        ]
        contents = self.app.get("/dashboards").get_data(as_text=True)
        self.assertIn('class="table-warning"', contents)  # transient
        self.assertIn('class="table-danger"', contents)  # chronic
        self.assertIn("failing for 9 runs", contents)
        self.assertIn("failing for 1 run", contents)  # singular

    def test_browse_shows_last_success(self):
        self.mock_registry.list_dashboards.return_value = [
            self._dashboard(
                "Broken",
                "Broken",
                latest_status="FAIL",
                latest_finished_at=datetime(2026, 9, 13, 10, 0, 0),
                last_success_at=datetime(2026, 8, 20, 9, 0, 0),
                failures_since_success=2,
            ),
            self._dashboard(
                "NeverOK", "NeverOK", latest_status="FAIL", failures_since_success=5
            ),
        ]
        contents = self.app.get("/dashboards").get_data(as_text=True)
        self.assertIn("<th>Last success</th>", contents)
        # A dashboard that has succeeded before shows the success timestamp;
        self.assertIn("2026-08-20 09:00:00", contents)
        # one that never has shows "never".
        self.assertIn("never", contents)

    def test_browse_root_autocomplete_datalist(self):
        self.mock_registry.list_roots.return_value = ["WikiProject Books", "Jean-Fred"]
        contents = self.app.get("/dashboards").get_data(as_text=True)
        self.assertIn('<datalist id="root-options">', contents)
        self.assertIn('value="WikiProject Books"', contents)
        self.assertIn('value="Jean-Fred"', contents)

    def test_browse_filtered_by_wiki(self):
        self.app.get("/dashboards?wiki=meta.wikimedia.org")
        self.mock_registry.list_dashboards.assert_called_once_with(
            site_hostname="meta.wikimedia.org",
            namespace_canonical=None,
            root_page=None,
            search=None,
            status=None,
        )

    def test_browse_filtered_by_namespace(self):
        self.app.get("/dashboards?namespace=User")
        self.mock_registry.list_dashboards.assert_called_once_with(
            site_hostname=None,
            namespace_canonical="User",
            root_page=None,
            search=None,
            status=None,
        )

    def test_browse_filtered_by_root(self):
        self.app.get("/dashboards?root=WikiProject+Music")
        self.mock_registry.list_dashboards.assert_called_once_with(
            site_hostname=None,
            namespace_canonical=None,
            root_page="WikiProject Music",
            search=None,
            status=None,
        )

    def test_browse_filtered_by_search(self):
        self.app.get("/dashboards?search=coverage")
        self.mock_registry.list_dashboards.assert_called_once_with(
            site_hostname=None,
            namespace_canonical=None,
            root_page=None,
            search="coverage",
            status=None,
        )

    def test_browse_htmx_request_returns_full_page_with_browse_content(self):
        """htmx uses hx-select to extract #browse-content client-side."""
        self.mock_registry.list_dashboards.return_value = [
            self._dashboard("My Dashboard", "My Dashboard"),
        ]
        response = self.app.get("/dashboards", headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 200)
        contents = response.get_data(as_text=True)
        # Full page returned (htmx extracts #browse-content via hx-select).
        self.assertIn("My Dashboard", contents)
        self.assertIn('id="browse-content"', contents)

    def test_browse_empty(self):
        response = self.app.get("/dashboards")
        self.assertEqual(response.status_code, 200)
        self.assertIn("No dashboards registered yet.", response.get_data(as_text=True))

    def test_browse_filtered_empty_message(self):
        response = self.app.get("/dashboards?search=nomatch")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "No dashboards match these filters.", response.get_data(as_text=True)
        )

    def test_dashboards_filtered_by_status(self):
        self.app.get("/dashboards?status=FAIL")
        self.mock_registry.list_dashboards.assert_called_once_with(
            site_hostname=None,
            namespace_canonical=None,
            root_page=None,
            search=None,
            status="FAIL",
        )

    def test_dashboards_status_control_reflects_selection(self):
        contents = self.app.get("/dashboards?status=FAIL").get_data(as_text=True)
        # The Status select renders and marks the chosen option selected.
        self.assertIn('name="status"', contents)
        self.assertIn('value="FAIL" selected', contents)

    def test_browse_redirects_to_dashboards(self):
        """The legacy /browse URL 301-redirects to /dashboards, keeping filters."""
        response = self.app.get("/browse?wiki=meta.wikimedia.org")
        self.assertEqual(response.status_code, 301)
        self.assertIn("/dashboards", response.headers["Location"])
        self.assertIn("wiki=meta.wikimedia.org", response.headers["Location"])


class RunsTests(AppTests):
    def setUp(self):
        super().setUp()
        patcher = patch("integraality.app.DashboardRegistry", autospec=True)
        self.mock_registry_cls = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_registry = self.mock_registry_cls.return_value.__enter__.return_value
        self.mock_registry.list_runs.return_value = []

    def _run(self, title, status="OK", **fields):
        row = {
            "page_url": "https://www.wikidata.org/wiki/{}".format(
                title.replace(" ", "_")
            ),
            "page_title": title,
            "site_hostname": "www.wikidata.org",
            "site_name": "Wikidata",
            "finished_at": datetime(2026, 9, 11, 10, 0, 0),
            "status": status,
            "trigger_source": "CRON",
            "duration_ms": 72000,
            "sparql_engine": "Wikidata Query Service",
            "error_category": None,
            "error_detail": None,
            "entity_total": 39163,
            "grouping_count": 40,
            "column_count": 7,
        }
        row.update(fields)
        return row

    def test_runs_lists_recent_runs_ok_and_fail(self):
        self.mock_registry.list_runs.return_value = [
            self._run(
                "Broken",
                status="FAIL",
                error_category="query",
                error_detail="SPARQL timeout",
            ),
            self._run("Healthy", status="OK"),
        ]
        contents = self.app.get("/runs").get_data(as_text=True)
        self.assertIn("Broken", contents)
        self.assertIn("Healthy", contents)
        self.assertIn("text-bg-danger", contents)  # FAIL badge
        self.assertIn("text-bg-success", contents)  # OK badge
        self.assertIn("SPARQL timeout", contents)
        self.assertIn("CRON", contents)  # trigger column
        self.assertIn("72.0s", contents)  # duration column (72000ms -> 72.0s)

    def test_runs_empty(self):
        contents = self.app.get("/runs").get_data(as_text=True)
        self.assertIn("No runs recorded yet.", contents)

    def test_runs_scoped_to_wiki(self):
        self.app.get("/runs?wiki=commons.wikimedia.org")
        self.mock_registry.list_runs.assert_called_once_with(
            site_hostname="commons.wikimedia.org",
        )


class DashboardHistoryTests(AppTests):
    def setUp(self):
        super().setUp()
        patcher = patch("integraality.app.DashboardRegistry", autospec=True)
        self.mock_registry_cls = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_registry = self.mock_registry_cls.return_value.__enter__.return_value
        self.mock_registry.get_dashboard.return_value = {
            "page_url": "https://www.wikidata.org/wiki/Wikidata:Test",
            "page_title": "Wikidata:Test",
            "namespace_canonical": "Project",
            "namespace_localized": "Wikidata",
            "root_page": "Test",
            "site_hostname": "www.wikidata.org",
            "site_name": "Wikidata",
        }
        self.mock_registry.list_dashboard_run_history.return_value = []
        # Run the *real* compute_health over the mocked history rows (it's a
        # pure staticmethod), so the route + summary integration is exercised
        # rather than a hand-built fixture that can drift from real output.
        self.mock_registry.compute_health.side_effect = DashboardRegistry.compute_health

    def _run(self, finished_at, status="OK", **fields):
        row = {
            "finished_at": datetime.strptime(finished_at, "%Y-%m-%d %H:%M:%S"),
            "status": status,
            "trigger_source": "CRON",
            "duration_ms": 60000,
            "sparql_engine": "Wikidata Query Service",
            "error_category": None,
            "error_detail": None,
            "revision_id": 12345,
            "entity_total": 180579,
            "grouping_count": 34,
            "column_count": 9,
        }
        row.update(fields)
        return row

    def test_dashboard_unknown_returns_404(self):
        self.mock_registry.get_dashboard.return_value = None
        response = self.app.get("/dashboard?wiki=www.wikidata.org&page=Nope")
        self.assertEqual(response.status_code, 404)

    def test_dashboard_no_runs(self):
        contents = self.app.get(
            "/dashboard?wiki=www.wikidata.org&page=Wikidata:Test"
        ).get_data(as_text=True)
        self.assertIn("Wikidata:Test", contents)
        self.assertIn("No runs recorded yet for this dashboard.", contents)

    def test_dashboard_renders_trend_and_health(self):
        history = [
            self._run(
                "2019-05-22 20:28:56",
                entity_total=180579,
                grouping_count=2,
                trigger_source="WEB",
            ),
            self._run("2025-12-19 01:04:35", entity_total=381218, grouping_count=155),
            self._run(
                "2026-01-16 01:03:00",
                status="FAIL",
                error_category="query",
                error_detail="SPARQL parse error",
                revision_id=None,
                duration_ms=800,
                entity_total=None,
                grouping_count=None,
                column_count=None,
            ),
        ]
        self.mock_registry.list_dashboard_run_history.return_value = history

        response = self.app.get("/dashboard?wiki=www.wikidata.org&page=Wikidata:Test")
        self.assertEqual(response.status_code, 200)
        contents = response.get_data(as_text=True)

        # Behavioral: the run data reaches the page (health + chart series).
        self.assertIn("Wikidata:Test", contents)  # header
        self.assertIn("Failing", contents)  # 1 trailing failure -> failing badge
        self.assertIn("query", contents)  # error category surfaced
        self.assertIn("381218", contents)  # latest entity_total in chart JSON
        self.assertIn("381,218", contents)  # thousands-formatted, reaches the page
        # Charts load from the pinned cdnjs mirror (repo JS constraint), and the
        # server-rendered runs table works without JS.
        self.assertIn("tools-static.wmflabs.org/cdnjs", contents)
        self.assertIn("<table", contents)
        # A11y: the decorative run-tick strip is hidden from AT (table carries
        # the same data); the wide runs table scrolls on mobile.
        self.assertIn("run-strip", contents)
        self.assertIn('aria-hidden="true"', contents)
        self.assertIn("table-responsive", contents)
        # Engagement (1 WEB of 3 runs) surfaced from the real compute_health.
        self.assertIn("Manual refreshes", contents)
        self.assertIn("33.3%", contents)  # web_share 1/3
        self.assertIn("1 of 3 runs manual", contents)

    def test_dashboard_passes_identity_to_registry(self):
        self.app.get("/dashboard?wiki=commons.wikimedia.org&page=Foo")
        self.mock_registry.get_dashboard.assert_called_once_with(
            "commons.wikimedia.org", "Foo"
        )
        self.mock_registry.list_dashboard_run_history.assert_called_once_with(
            "commons.wikimedia.org", "Foo"
        )

    def test_dashboard_runs_table_capped(self):
        """The runs table shows at most RUNS_TABLE_CAP rows with a
        'latest N of M' note; charts/health still consume the full history."""
        n = RUNS_TABLE_CAP + 10
        history = [
            self._run(f"2020-01-01 00:{i // 60:02d}:{i % 60:02d}", revision_id=1000 + i)
            for i in range(n)
        ]
        self.mock_registry.list_dashboard_run_history.return_value = history

        contents = self.app.get(
            "/dashboard?wiki=www.wikidata.org&page=Wikidata:Test"
        ).get_data(as_text=True)

        # Note reflects the cap and the true total.
        self.assertIn(f"latest {RUNS_TABLE_CAP} of {n}", contents)
        # At most RUNS_TABLE_CAP data rows rendered (count <tr> in <tbody>).
        body = contents.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        self.assertEqual(body.count("<tr"), RUNS_TABLE_CAP)

    def test_dashboard_hides_duration_chart_when_no_duration(self):
        """No run has a duration -> the Run duration heading/box is not rendered
        (rather than a titled empty 280px box)."""
        history = [self._run("2020-01-01 00:00:00", duration_ms=None)]
        self.mock_registry.list_dashboard_run_history.return_value = history

        contents = self.app.get(
            "/dashboard?wiki=www.wikidata.org&page=Wikidata:Test"
        ).get_data(as_text=True)

        self.assertNotIn("Run duration", contents)
        self.assertNotIn('id="duration-chart"', contents)
        # The trend chart is still there.
        self.assertIn('id="trend-chart"', contents)


class PagesProcessorTests(AppTests):
    def setUp(self):
        super().setUp()
        patcher = patch("integraality.app.PagesProcessor", autospec=True)
        self.mock_pages_processor = patcher.start()
        self.addCleanup(patcher.stop)
        self.page_title = "Foo"
        self.page_url = f"https://wikidata.org/wiki/{self.page_title}"
        self.linked_page = f'<a href="{self.page_url}">{self.page_title}</a>'

    def assertSuccessPage(self, response, message):
        """A custom assertion for a success page."""
        self.assertEqual(response.status_code, 200)
        contents = response.get_data(as_text=True)
        self.assertIn("alert-success", contents)
        self.assertPresent(message, contents)

    def assertErrorPage(self, response, message, expected_status=200):
        """A custom assertion for an error page."""
        self.assertEqual(response.status_code, expected_status)
        contents = response.get_data(as_text=True)
        self.assertIn("alert-danger", contents)
        self.assertPresent(message, contents)

    def assertPresent(self, message, response):
        self.assertIn(
            message.replace(" ", "").replace("\t", "").replace("\n", ""),
            response.replace(" ", "").replace("\t", "").replace("\n", ""),
        )


class UpdateTests(PagesProcessorTests):
    def test_update_stream_page(self):
        response = self.app.get(f"/update?page={self.page_title}&url={self.page_url}")
        self.assertEqual(response.status_code, 200)
        contents = response.get_data(as_text=True)
        self.assertIn("EventSource", contents)
        self.assertIn(self.page_title, contents)

    def test_update_stream_endpoint(self):
        self.mock_pages_processor.return_value.process_one_page.return_value = 1.23
        response = self.app.get(
            f"/update/stream?page={self.page_title}&url={self.page_url}"
        )
        self.assertIn("text/event-stream", response.content_type)

    def _parse_sse_events(self, response):
        """Parse SSE events from a streaming response into a list of dicts."""
        data = response.get_data(as_text=True)
        events = []
        for line in data.strip().split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: ") :]))
        return events

    def test_update_stream_success_end_to_end(self):
        self.mock_pages_processor.return_value.process_one_page.return_value = 4.56
        response = self.app.get(
            f"/update/stream?page={self.page_title}&url={self.page_url}"
        )
        events = self._parse_sse_events(response)
        self.assertTrue(len(events) >= 1)
        done_event = events[-1]
        self.assertEqual(done_event["status"], "done")
        self.assertEqual(done_event["result"], 4.56)

    def test_update_stream_error_query_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = (
            QueryTimeoutException("Timeout", "SELECT ?x WHERE { ?x wdt:P31 wd:Q5 }")
        )
        response = self.app.get(
            f"/update/stream?page={self.page_title}&url={self.page_url}"
        )
        events = self._parse_sse_events(response)
        error_event = events[-1]
        self.assertEqual(error_event["status"], "error")
        self.assertEqual(error_event["error_type"], "QueryTimeoutException")
        self.assertEqual(error_event["error_category"], "timeout")
        self.assertEqual(error_event["query"], "SELECT ?x WHERE { ?x wdt:P31 wd:Q5 }")
        self.assertIn("Timeout", error_event["message"])

    def test_update_stream_error_transient_server_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = (
            TransientServerException("503 Service Unavailable")
        )
        response = self.app.get(
            f"/update/stream?page={self.page_title}&url={self.page_url}"
        )
        events = self._parse_sse_events(response)
        error_event = events[-1]
        self.assertEqual(error_event["status"], "error")
        self.assertEqual(error_event["error_type"], "TransientServerException")
        self.assertEqual(error_event["error_category"], "transient")
        self.assertIn("503", error_event["message"])

    def test_update_stream_error_processing_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = (
            ProcessingException("Bad config")
        )
        response = self.app.get(
            f"/update/stream?page={self.page_title}&url={self.page_url}"
        )
        events = self._parse_sse_events(response)
        error_event = events[-1]
        self.assertEqual(error_event["status"], "error")
        self.assertEqual(error_event["error_type"], "ProcessingException")
        self.assertEqual(error_event["error_category"], "config")
        self.assertIn("Bad config", error_event["message"])

    def test_update_stream_error_unknown_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = (
            RuntimeError("unexpected")
        )
        response = self.app.get(
            f"/update/stream?page={self.page_title}&url={self.page_url}"
        )
        events = self._parse_sse_events(response)
        error_event = events[-1]
        self.assertEqual(error_event["status"], "error")
        self.assertEqual(error_event["error_type"], "RuntimeError")
        self.assertEqual(error_event["error_category"], "error")
        self.assertIn("unexpected", error_event["message"])
        self.assertIn("traceback", error_event)

    def test_update_success(self):
        response = self.app.get(
            f"/update?page={self.page_title}&url={self.page_url}&nostream"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(
            page_title=self.page_title
        )
        message = f"Updated page {self.linked_page}"
        self.assertSuccessPage(response, message)

    def test_update_error_processing_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = (
            ProcessingException
        )
        response = self.app.get(
            f"/update?page={self.page_title}&url={self.page_url}&nostream"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(
            page_title=self.page_title
        )
        message = f"<p>Something went wrong when updating page {self.linked_page}. Please check your configuration.</p>"
        self.assertErrorPage(response, message, expected_status=422)

    def test_update_error_unknown_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = ValueError
        response = self.app.get(
            f"/update?page={self.page_title}&url={self.page_url}&nostream"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(
            page_title=self.page_title
        )
        message = f"<p>Something catastrophic happened when processing page {self.linked_page}.</p>"
        self.assertErrorPage(response, message, expected_status=500)

    def test_update_error_query_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = (
            QueryException("Error", "SELECT X")
        )
        response = self.app.get(
            f"/update?page={self.page_title}&url={self.page_url}&nostream"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(
            page_title=self.page_title
        )
        expected = (
            '<p>Something went wrong when updating page <a href="https://wikidata.org/wiki/Foo">Foo</a>.</p>\n'
            "<p>The following SPARQL query timed out or returned no result:</p>\n"
            "<pre><code>SELECT X</code></pre>\n"
        )
        self.assertErrorPage(response, expected, expected_status=422)
        buttons = (
            '<a class="btn btn-primary" href="https://query.wikidata.org/#SELECT X">Try it in Wikidata Query Service</a>'
            '<a class="btn btn-info" href="https://qlever.dev/wikidata/?query='
        )
        self.assertErrorPage(response, buttons, expected_status=422)

    def test_update_success_meta(self):
        page_url = f"https://meta.wikimedia.org/wiki/{self.page_title}"
        response = self.app.get(
            f"/update?page={self.page_title}&url={page_url}&nostream"
        )
        self.mock_pages_processor.assert_called_once_with(page_url)
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(
            page_title=self.page_title
        )
        message = f'Updated page <a href="{page_url}">{self.page_title}</a>'
        self.assertSuccessPage(response, message)


class QueriesTests(PagesProcessorTests):
    def setUp(self):
        super().setUp()

        patcher_qlever = patch(
            "integraality.app.get_qlever_ui_url",
            return_value="https://qlever.dev/wikidata/",
        )
        patcher_qlever.start()
        self.addCleanup(patcher_qlever.stop)

        self.column_P1 = column.PropertyColumn(property="P1")
        self.column_Lbr = column.LabelColumn(language="br")
        self.column_Dbr = column.DescriptionColumn(language="br")

        patcher04 = patch("integraality.grouping.GroupingConfiguration", autospec=True)
        self.mock_grouping_configuration = patcher04.start()
        self.addCleanup(patcher04.stop)
        self.mock_grouping_configuration.format_predicate_html.return_value = (
            '<a href="https://wikidata.org/wiki/Property:P495">P495</a>'
        )
        self.mock_grouping_configuration.property = "P495"

        patcher1 = patch(
            "integraality.pages_processor.PropertyStatistics", autospec=True
        )
        self.mock_property_statistics = patcher1.start()
        self.mock_property_statistics.grouping_configuration = (
            self.mock_grouping_configuration
        )
        self.mock_property_statistics.columns = {
            "P1": self.column_P1,
            "Lbr": self.column_Lbr,
            "Dbr": self.column_Dbr,
        }
        self.addCleanup(patcher1.stop)

    def _make_query_data(self, col, positive="X", negative="Z"):
        return {
            "column": col,
            "positive_query": positive,
            "negative_query": negative,
            "formatted_predicate": self.mock_grouping_configuration.format_predicate_html(),
        }

    def test_queries_success(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics
        self.mock_property_statistics.get_queries_for_column.return_value = (
            self._make_query_data(self.column_P1)
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&column=P1&grouping=Q2"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )
        self.mock_property_statistics.get_queries_for_column.assert_called_once_with(
            "P1", "Q2"
        )
        self.assertEqual(response.status_code, 200)
        content = response.get_data(as_text=True)
        expected_body = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            '<a href="https://wikidata.org/wiki/Property:P1">P1</a>, '
            'with <a href="https://wikidata.org/wiki/Q2">Q2</a> as <a href="https://wikidata.org/wiki/Property:P495">P495</a>.</p>\n\t'
        )
        self.assertPresent(expected_body, content)
        expected_wdqs = (
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">WDQS: All items with the property set</a>'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">WDQS: All items without the property set</a>'
        )
        self.assertPresent(expected_wdqs, content)
        expected_qlever = (
            '<a class="btn btn-info" href="https://qlever.dev/wikidata/?query='
        )
        self.assertPresent(expected_qlever, content)

    def test_queries_success_no_grouping(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics
        self.mock_property_statistics.get_queries_for_column.return_value = (
            self._make_query_data(self.column_P1)
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&column=P1&grouping=None"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )
        self.mock_property_statistics.get_queries_for_column.assert_called_once_with(
            "P1", "None"
        )
        self.assertEqual(response.status_code, 200)
        content = response.get_data(as_text=True)
        expected_body = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            '<a href="https://wikidata.org/wiki/Property:P1">P1</a>, '
            'without <a href="https://wikidata.org/wiki/Property:P495">P495</a> grouping.</p>\n\t'
        )
        self.assertPresent(expected_body, content)
        expected_wdqs = (
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">WDQS: All items with the property set</a>'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">WDQS: All items without the property set</a>'
        )
        self.assertPresent(expected_wdqs, content)
        expected_qlever = (
            '<a class="btn btn-info" href="https://qlever.dev/wikidata/?query='
        )
        self.assertPresent(expected_qlever, content)

    def test_queries_success_labels(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics
        self.mock_property_statistics.get_queries_for_column.return_value = (
            self._make_query_data(self.column_Lbr)
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&column=Lbr&grouping=Q2"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )
        self.mock_property_statistics.get_queries_for_column.assert_called_once_with(
            "Lbr", "Q2"
        )
        self.assertEqual(response.status_code, 200)
        content = response.get_data(as_text=True)
        expected_body = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            "br label, "
            'with <a href="https://wikidata.org/wiki/Q2">Q2</a> as <a href="https://wikidata.org/wiki/Property:P495">P495</a>.</p>\n\t'
        )
        self.assertPresent(expected_body, content)
        expected_wdqs = (
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">WDQS: All items with the label set</a>'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">WDQS: All items without the label set</a>'
        )
        self.assertPresent(expected_wdqs, content)
        expected_qlever = (
            '<a class="btn btn-info" href="https://qlever.dev/wikidata/?query='
        )
        self.assertPresent(expected_qlever, content)

    def test_queries_success_descriptions(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics
        self.mock_property_statistics.get_queries_for_column.return_value = (
            self._make_query_data(self.column_Dbr)
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&column=Dbr&grouping=Q2"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )
        self.mock_property_statistics.get_queries_for_column.assert_called_once_with(
            "Dbr", "Q2"
        )
        self.assertEqual(response.status_code, 200)
        content = response.get_data(as_text=True)
        expected_body = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            "br description, "
            'with <a href="https://wikidata.org/wiki/Q2">Q2</a> as <a href="https://wikidata.org/wiki/Property:P495">P495</a>.</p>\n\t'
        )
        self.assertPresent(expected_body, content)
        expected_wdqs = (
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">WDQS: All items with the description set</a>'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">WDQS: All items without the description set</a>'
        )
        self.assertPresent(expected_wdqs, content)
        expected_qlever = (
            '<a class="btn btn-info" href="https://qlever.dev/wikidata/?query='
        )
        self.assertPresent(expected_qlever, content)

    def test_queries_success_totals(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics
        self.mock_property_statistics.get_queries_for_column.return_value = (
            self._make_query_data(self.column_P1)
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&property=P1&grouping="
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )
        self.mock_property_statistics.get_queries_for_column.assert_called_once_with(
            "P1", ""
        )
        self.assertEqual(response.status_code, 200)
        content = response.get_data(as_text=True)
        expected_body = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            '<a href="https://wikidata.org/wiki/Property:P1">P1</a>, '
            "for the totals.</p>\n\t"
        )
        self.assertPresent(expected_body, content)
        expected_wdqs = (
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">WDQS: All items with the property set</a>'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">WDQS: All items without the property set</a>'
        )
        self.assertPresent(expected_wdqs, content)
        expected_qlever = (
            '<a class="btn btn-info" href="https://qlever.dev/wikidata/?query='
        )
        self.assertPresent(expected_qlever, content)

    def test_queries_error_processing_exception(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.side_effect = ProcessingException
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&property=P1&grouping=Q2"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )
        message = f"<p>Something went wrong when generating queries from page {self.linked_page}.</p>"
        self.assertErrorPage(response, message, expected_status=422)

    def test_queries_error_unknown_exception(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.side_effect = ValueError
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&property=P1&grouping=Q2"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )
        message = f"<p>Something catastrophic happened when generating queries from page {self.linked_page}.</p>"
        self.assertErrorPage(response, message, expected_status=500)

    def test_queries_error_transient_exception(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.side_effect = TransientServerException(
            "maxlag"
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&property=P1&grouping=Q2"
        )
        self.assertEqual(response.status_code, 503)
        contents = response.get_data(as_text=True)
        self.assertIn("alert-warning", contents)
        message = f"A temporary server issue occurred when generating queries from page {self.linked_page}."
        self.assertPresent(message, contents)

    def test_queries_success_unknown_value_grouping(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics
        self.mock_property_statistics.get_queries_for_column.return_value = (
            self._make_query_data(self.column_P1)
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&column=P1&grouping=UNKNOWN_VALUE"
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )
        self.mock_property_statistics.get_queries_for_column.assert_called_once_with(
            "P1", "UNKNOWN_VALUE"
        )
        self.assertEqual(response.status_code, 200)
        content = response.get_data(as_text=True)
        expected_body = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            '<a href="https://wikidata.org/wiki/Property:P1">P1</a>, '
            'with unknown value as <a href="https://wikidata.org/wiki/Property:P495">P495</a>.</p>\n\t'
        )
        self.assertPresent(expected_body, content)
        expected_wdqs = (
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">WDQS: All items with the property set</a>'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">WDQS: All items without the property set</a>'
        )
        self.assertPresent(expected_wdqs, content)
        expected_qlever = (
            '<a class="btn btn-info" href="https://qlever.dev/wikidata/?query='
        )
        self.assertPresent(expected_qlever, content)

    def test_queries_json_format(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics
        self.mock_property_statistics.get_queries_for_column.return_value = (
            self._make_query_data(
                self.column_P1, positive="SELECT ?x", negative="SELECT ?y"
            )
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&column=P1&grouping=Q2&format=json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(
            response.get_json(),
            {
                "page_title": self.page_title,
                "page_url": self.page_url,
                "column": "P1",
                "grouping": "Q2",
                "formatted_predicate": '<a href="https://wikidata.org/wiki/Property:P495">P495</a>',
                "positive_query": "SELECT ?x",
                "negative_query": "SELECT ?y",
                "qlever_ui_url": "https://qlever.dev/wikidata/",
            },
        )

    def test_queries_json_format_processing_exception(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.side_effect = ProcessingException(
            "bad config"
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&column=P1&grouping=Q2&format=json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.get_json(), {"error": "bad config"})

    def test_queries_json_format_unknown_exception(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.side_effect = ValueError(
            "boom"
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&column=P1&grouping=Q2&format=json"
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.get_json(), {"error": "boom"})

    def test_queries_json_format_transient_exception(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.side_effect = TransientServerException(
            "maxlag"
        )
        response = self.app.get(
            f"/queries?page={self.page_title}&url={self.page_url}&column=P1&grouping=Q2&format=json"
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.get_json(), {"error": "maxlag"})
