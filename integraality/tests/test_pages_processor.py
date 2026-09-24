"""Unit tests for pages_processor.py."""

import argparse
import unittest
from unittest.mock import MagicMock, patch

import fakeredis

from ..column import ColumnMaker
from ..grouping import GroupingConfiguration
from ..pages_processor import (
    ConfigException,
    NoEndTemplateException,
    NoStartTemplateException,
    PagesProcessor,
    RunContext,
    TransientServerException,
    UnsupportedWikiException,
    main,
    validate_wiki_url,
)
from ..sparql_utils import QueryException, QueryTimeoutException, SparqlQueryEngine


class RecordingEngine(SparqlQueryEngine):
    """A picklable engine that counts live queries (class-level, so the count
    survives the Redis pickle round-trip) and returns a dateTime datatype."""

    name = "Recording"
    calls = 0

    def _do_select(self, query):
        type(self).calls += 1
        return [{"datatype": "http://www.w3.org/2001/XMLSchema#dateTime"}]


class ValidateWikiUrlTest(unittest.TestCase):
    def test_accepts_supported_wikis(self):
        for url, host in [
            ("https://www.wikidata.org/wiki/", "www.wikidata.org"),
            ("https://commons.wikimedia.org/wiki/", "commons.wikimedia.org"),
            ("https://meta.wikimedia.org/wiki/", "meta.wikimedia.org"),
        ]:
            self.assertEqual(validate_wiki_url(url), host)

    def test_rejects_unsupported_wiki_family(self):
        # Not supported yet -- widen ALLOWED_WIKI_DOMAINS when adding support.
        for url in [
            "https://he.wikipedia.org/wiki/",
            "https://fr.wiktionary.org/wiki/",
        ]:
            with self.assertRaises(UnsupportedWikiException):
                validate_wiki_url(url)

    def test_rejects_non_wikimedia_host(self):
        with self.assertRaises(UnsupportedWikiException):
            validate_wiki_url("https://proxy.example/https/www.wikidata.org/wiki/")

    def test_rejects_lookalike_suffix(self):
        # A host that merely contains a Wikimedia domain but isn't a subdomain.
        with self.assertRaises(UnsupportedWikiException):
            validate_wiki_url("https://wikidata.org.evil.example/wiki/")

    def test_rejects_proxy_encoding_wiki_in_subdomain(self):
        # Open proxies encode the real target into their own host, e.g.
        # www.wikidata.org.<proxy> or dash-style www-wikidata-org.<proxy>.
        for url in [
            "https://www.wikidata.org.proxy.example/wiki/Foo",
            "https://www-wikidata-org.proxy.example/wiki/Foo",
        ]:
            with self.assertRaises(UnsupportedWikiException):
                validate_wiki_url(url)

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(UnsupportedWikiException):
            validate_wiki_url("file:///etc/passwd")

    def test_rejects_bytes_url_without_crashing(self):
        with self.assertRaises(UnsupportedWikiException):
            validate_wiki_url(b"https://proxy.example/")

    def test_constructor_rejects_bad_url(self):
        with self.assertRaises(UnsupportedWikiException):
            PagesProcessor(url="https://proxy.example/https/www.wikidata.org/wiki/")


class ProcessortTest(unittest.TestCase):
    def setUp(self):
        fake_cache_client = fakeredis.FakeStrictRedis()
        self.processor = PagesProcessor(cache_client=fake_cache_client)


class TestGroupingTypeCaching(ProcessortTest):
    """The grouping type is resolved before caching, so a cache hit builds a
    PropertyStatistics without re-running the live type-detection query."""

    def _unresolved_config(self, engine):
        return {
            "selector_sparql": "wdt:P31 wd:Q5",
            "columns": [ColumnMaker.make("P585", None)],
            "grouping_configuration": GroupingConfiguration(predicate="wdt:P585"),
            "grouping_link_mode": "link",
            "sparql_query_engine": engine,
        }

    def _patched_page(self, engine):
        """Stub the assembler so parse_config yields our unresolved config."""
        start_tpl = MagicMock()
        start_tpl.title.return_value = "Property dashboard"
        end_tpl = MagicMock()
        end_tpl.title.return_value = "Property dashboard end"
        page = MagicMock()
        page.title.return_value = "User:Foo/Dashboard"
        page.templatesWithParams.return_value = [(start_tpl, []), (end_tpl, [])]
        assembler = self.processor.config_assembler
        return page, (
            patch.object(assembler, "parse_config_from_params", return_value={}),
            patch.object(
                assembler,
                "parse_config",
                return_value=self._unresolved_config(engine),
            ),
        )

    def test_cache_hit_does_not_query(self):
        RecordingEngine.calls = 0
        engine = RecordingEngine()
        page, patches = self._patched_page(engine)
        with patches[0], patches[1]:
            self.processor.make_stats_object_arguments_for_page(page)

        # The cached config carries a resolved type...
        cached = self.processor.cache.get_cache_value(
            self.processor.make_cache_key(page.title())
        )
        self.assertIsNotNone(cached["grouping_configuration"].grouping_type)

        # ...so a cache hit rebuilds PropertyStatistics with no live query.
        RecordingEngine.calls = 0
        stats = self.processor.make_stats_object_for_page_title(page.title())
        self.assertEqual(RecordingEngine.calls, 0)
        self.assertIsNotNone(stats.grouping_configuration.grouping_type)


class TestReplaceInPage(ProcessortTest):
    def setUp(self):
        self.processor = PagesProcessor()
        self.text = """
Head
{{Property dashboard start
|properties=P136:genre,P404
|grouping_property=P400
|row_no_group=1
|selector_sparql=wdt:P31/wdt:P279* wd:Q7889
|target_page_title=Wikidata:WikiProject Video games/Statistics/Platform
|grouping_link=Wikidata::WikiProject Video games/Reports/Platform
}}
foo
{{Property dashboard end}}
Bottom
"""
        self.final_text = """
Head
{{Property dashboard start
|properties=P136:genre,P404
|grouping_property=P400
|row_no_group=1
|selector_sparql=wdt:P31/wdt:P279* wd:Q7889
|target_page_title=Wikidata:WikiProject Video games/Statistics/Platform
|grouping_link=Wikidata::WikiProject Video games/Reports/Platform
}}
bar
{{Property dashboard end}}
Bottom
"""

    def test_replace_in_page(self):
        result = self.processor.replace_in_page("bar", self.text)
        self.assertEqual(result, self.final_text)

    def test_replace_in_page_escaped_pipe(self):
        text = self.text.replace("wd:Q7889", "{{!}}")
        final_text = self.final_text.replace("wd:Q7889", "{{!}}")
        result = self.processor.replace_in_page("bar", text)
        self.assertEqual(result, final_text)


class TestMigrateTemplateParams(ProcessortTest):
    def test_renames_deprecated_param(self):
        text = (
            "{{Property dashboard\n|stats_for_no_group=1\n}}\n"
            "table\n{{Property dashboard end}}"
        )
        result = self.processor.migrate_template_params(text)
        self.assertIn("|row_no_group=1", result)
        self.assertNotIn("stats_for_no_group", result)

    def test_leaves_current_param_unchanged(self):
        text = (
            "{{Property dashboard\n|row_no_group=1\n}}\n"
            "table\n{{Property dashboard end}}"
        )
        result = self.processor.migrate_template_params(text)
        self.assertEqual(result, text)

    def test_no_false_match(self):
        text = (
            "{{Property dashboard\n|properties=P136\n}}\n"
            "table\n{{Property dashboard end}}"
        )
        result = self.processor.migrate_template_params(text)
        self.assertEqual(result, text)

    def test_does_not_match_substring(self):
        """A param whose name contains the old name as a substring is not affected."""
        text = (
            "{{Property dashboard\n|my_stats_for_no_group=1\n}}\n"
            "table\n{{Property dashboard end}}"
        )
        result = self.processor.migrate_template_params(text)
        self.assertEqual(result, text)

    def test_scoped_to_template(self):
        """Text outside the template block is not modified."""
        text = (
            "Some docs mentioning |stats_for_no_group=1 outside.\n"
            "{{Property dashboard\n|stats_for_no_group=1\n}}\n"
            "Table content\n"
            "{{Property dashboard end}}"
        )
        result = self.processor.migrate_template_params(text)
        self.assertIn("|row_no_group=1", result)
        # The occurrence outside the template is preserved
        self.assertIn("Some docs mentioning |stats_for_no_group=1 outside.", result)


class TestMain(unittest.TestCase):
    def setUp(self):
        patcher1 = patch("integraality.pages_processor.PagesProcessor", autospec=True)
        self.mock_pages_processor = patcher1.start()
        self.addCleanup(patcher1.stop)

        patcher2 = patch("argparse.ArgumentParser.parse_args", autospec=True)
        self.mock_args = patcher2.start()
        self.addCleanup(patcher2.stop)

    def test_main_url_argument(self):
        url = "Foo"
        self.mock_args.return_value = argparse.Namespace(
            url=url,
            warm_cache_only=False,
            populate_registry=False,
            page=None,
            limit=None,
        )
        main()
        self.mock_pages_processor.assert_called_once_with(url)
        self.mock_pages_processor.return_value.process_all.assert_called_once_with(
            limit=None
        )

    def test_main_page_argument(self):
        url = "Foo"
        self.mock_args.return_value = argparse.Namespace(
            url=url,
            warm_cache_only=False,
            populate_registry=False,
            page="Bar/Dashboard",
            limit=None,
        )
        main()
        self.mock_pages_processor.assert_called_once_with(url)
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(
            "Bar/Dashboard"
        )

    def test_main_populate_registry_argument(self):
        url = "Foo"
        self.mock_args.return_value = argparse.Namespace(
            url=url,
            warm_cache_only=False,
            populate_registry=True,
            page=None,
            limit=None,
        )
        main()
        self.mock_pages_processor.assert_called_once_with(url)
        self.mock_pages_processor.return_value.populate_registry.assert_called_once_with(
            limit=None
        )

    def test_main_limit_argument(self):
        url = "Foo"
        self.mock_args.return_value = argparse.Namespace(
            url=url,
            warm_cache_only=False,
            populate_registry=False,
            page=None,
            limit=5,
        )
        main()
        self.mock_pages_processor.return_value.process_all.assert_called_once_with(
            limit=5
        )

    def test_main_limit_argument_with_populate_registry(self):
        url = "Foo"
        self.mock_args.return_value = argparse.Namespace(
            url=url,
            warm_cache_only=False,
            populate_registry=True,
            page=None,
            limit=5,
        )
        main()
        self.mock_pages_processor.return_value.populate_registry.assert_called_once_with(
            limit=5
        )


class TestPopulateRegistryDerivesBrowseDimensions(ProcessortTest):
    """populate_registry validates pages and derives browse dimensions."""

    def _dashboard_page(self):
        """A mock page that looks like a genuine dashboard."""
        namespace = MagicMock()
        namespace.canonical_name = "Project"
        namespace.custom_name = "Wikidata"

        page = MagicMock()
        page.site.hostname.return_value = "www.wikidata.org"
        page.pageid = 42
        page.full_url.return_value = (
            "https://www.wikidata.org/wiki/Wikidata:WikiProject_Music/Stats"
        )
        page.title.side_effect = lambda with_ns=True: (
            "Wikidata:WikiProject Music/Stats" if with_ns else "WikiProject Music/Stats"
        )
        page.site.siteinfo = {"sitename": "Wikidata"}
        page.namespace.return_value = namespace
        return page

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_derives_and_passes_browse_dimensions(self, mock_registry_cls):
        registry = mock_registry_cls.return_value.__enter__.return_value
        page = self._dashboard_page()

        with (
            patch.object(self.processor, "get_all_pages", return_value=[page]),
            patch.object(self.processor, "make_stats_object_arguments_for_page"),
        ):
            self.processor.populate_registry()

        registry.record.assert_called_once_with(
            site_hostname="www.wikidata.org",
            page_id=42,
            page_url="https://www.wikidata.org/wiki/Wikidata:WikiProject_Music/Stats",
            page_title="Wikidata:WikiProject Music/Stats",
            site_name="Wikidata",
            namespace_canonical="Project",
            namespace_localized="Wikidata",
            root_page="WikiProject Music",
        )

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_skips_phantom_page_with_no_start_template(self, mock_registry_cls):
        """A page with no START template merely transcludes a dashboard: skip."""
        registry = mock_registry_cls.return_value.__enter__.return_value
        page = self._dashboard_page()

        with (
            patch.object(self.processor, "get_all_pages", return_value=[page]),
            patch.object(
                self.processor,
                "make_stats_object_arguments_for_page",
                side_effect=NoStartTemplateException("no start"),
            ),
        ):
            self.processor.populate_registry()

        registry.record.assert_not_called()

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_records_dashboard_missing_end_template(self, mock_registry_cls):
        """A page with a start template but no end template is a misconfigured
        dashboard — still recorded, not treated as a phantom."""
        registry = mock_registry_cls.return_value.__enter__.return_value
        page = self._dashboard_page()

        with (
            patch.object(self.processor, "get_all_pages", return_value=[page]),
            patch.object(
                self.processor,
                "make_stats_object_arguments_for_page",
                side_effect=NoEndTemplateException("no end"),
            ),
        ):
            self.processor.populate_registry()

        registry.record.assert_called_once()

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_records_misconfigured_dashboard(self, mock_registry_cls):
        """A dashboard with a bad config is still recorded."""
        registry = mock_registry_cls.return_value.__enter__.return_value
        page = self._dashboard_page()

        with (
            patch.object(self.processor, "get_all_pages", return_value=[page]),
            patch.object(
                self.processor,
                "make_stats_object_arguments_for_page",
                side_effect=ConfigException("bad config"),
            ),
        ):
            self.processor.populate_registry()

        registry.record.assert_called_once()

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_uses_short_lived_connection_per_dashboard(self, mock_registry_cls):
        """Each recorded dashboard gets its own registry (connection), so a
        long crawl never outlives ToolsDB's idle timeout."""
        page_a = self._dashboard_page()
        page_b = self._dashboard_page()

        with (
            patch.object(
                self.processor, "get_all_pages", return_value=[page_a, page_b]
            ),
            patch.object(self.processor, "make_stats_object_arguments_for_page"),
        ):
            self.processor.populate_registry()

        # One registry instantiation (= one connection) per recorded page.
        self.assertEqual(mock_registry_cls.call_count, 2)

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_record_dashboard_returns_true_on_success(self, mock_registry_cls):
        self.assertTrue(self.processor._record_dashboard(self._dashboard_page()))

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_record_dashboard_returns_false_on_failure(self, mock_registry_cls):
        registry = mock_registry_cls.return_value.__enter__.return_value
        registry.record.side_effect = Exception("db gone")
        self.assertFalse(self.processor._record_dashboard(self._dashboard_page()))

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_populate_registry_survives_a_failed_record(self, mock_registry_cls):
        """A failed record is swallowed; the crawl continues over all pages."""
        registry = mock_registry_cls.return_value.__enter__.return_value
        # First page records fine, second fails.
        registry.record.side_effect = [None, Exception("db gone")]
        pages = [self._dashboard_page(), self._dashboard_page()]

        with (
            patch.object(self.processor, "get_all_pages", return_value=pages),
            patch.object(self.processor, "make_stats_object_arguments_for_page"),
        ):
            self.processor.populate_registry()  # must not raise

        self.assertEqual(registry.record.call_count, 2)


class TestRunRecording(ProcessortTest):
    """process_page's run-recording helpers (dashboard_runs)."""

    def _dashboard_page(self):
        namespace = MagicMock()
        namespace.canonical_name = "Project"
        namespace.custom_name = "Wikidata"
        page = MagicMock()
        page.site.hostname.return_value = "www.wikidata.org"
        page.pageid = 42
        page.full_url.return_value = "https://www.wikidata.org/wiki/Wikidata:Stats"
        page.title.side_effect = lambda with_ns=True: (
            "Wikidata:Stats" if with_ns else "Stats"
        )
        page.site.siteinfo = {"sitename": "Wikidata"}
        page.namespace.return_value = namespace
        return page

    def _stats(self):
        stats = MagicMock()
        stats.get_sparql_engine_name.return_value = "Wikidata Query Service"
        stats.columns = {"P1": object(), "P2": object()}
        stats.get_entity_total.return_value = 39163
        return stats

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_record_run_ok_sends_expected_fields(self, mock_registry_cls):
        registry = mock_registry_cls.return_value.__enter__.return_value

        self.processor._record_run_ok(
            self._dashboard_page(),
            trigger_source="CRON",
            elapsed_time=1.5,
            stats=self._stats(),
            groupings={"Q1": object(), "Q2": object(), "Q3": object()},
            report_groupings=[],
            revision_id=555,
        )

        registry.record_run.assert_called_once()
        _page_meta, run = registry.record_run.call_args[0]
        self.assertEqual(run.status, "OK")
        # Derived/computed fields (the wiring's actual logic):
        self.assertEqual(run.duration_ms, 1500)  # 1.5s -> ms
        self.assertEqual(run.grouping_count, 3)  # len(groupings)
        self.assertEqual(run.column_count, 2)  # len(stats.columns)
        self.assertEqual(run.entity_total, 39163)  # via stats.get_entity_total

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_record_run_fail_derives_category(self, mock_registry_cls):
        registry = mock_registry_cls.return_value.__enter__.return_value

        self.processor._record_run_fail(
            self._dashboard_page(),
            trigger_source="WEB",
            elapsed_time=0.2,
            exc=QueryTimeoutException("timeout", query="SELECT ?x"),
        )

        registry.record_run.assert_called_once()
        _page_meta, run = registry.record_run.call_args[0]
        self.assertEqual(run.status, "FAIL")
        self.assertEqual(run.error_category, "timeout")
        self.assertIn("timeout", run.error_detail)
        self.assertIsNone(run.revision_id)
        # No stats reached the failure site -> engine unknown.
        self.assertIsNone(run.sparql_engine)

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_record_run_fail_records_engine_when_known(self, mock_registry_cls):
        registry = mock_registry_cls.return_value.__enter__.return_value

        self.processor._record_run_fail(
            self._dashboard_page(),
            trigger_source="WEB",
            elapsed_time=0.2,
            exc=QueryTimeoutException("timeout", query="SELECT ?x"),
            sparql_engine="Wikidata Query Service",
        )

        registry.record_run.assert_called_once()
        _page_meta, run = registry.record_run.call_args[0]
        self.assertEqual(run.status, "FAIL")
        self.assertEqual(run.sparql_engine, "Wikidata Query Service")

    def test_make_stats_object_fills_run_context_engine(self):
        engine = MagicMock()
        engine.name = "QLever"
        config = {"sparql_query_engine": engine, "grouping_link_mode": "link"}
        run_context = RunContext()

        with (
            patch.object(
                self.processor,
                "make_stats_object_arguments_for_page",
                return_value=config,
            ),
            patch("integraality.pages_processor.PropertyStatistics"),
        ):
            self.processor.make_stats_object_for_page(
                self._dashboard_page(), run_context=run_context
            )

        self.assertEqual(run_context.sparql_engine, "QLever")

    def test_make_stats_object_fills_run_context_before_build_failure(self):
        # Engine is captured even when PropertyStatistics(**config) later fails.
        engine = MagicMock()
        engine.name = "QLever"
        config = {"sparql_query_engine": engine, "grouping_link_mode": "link"}
        run_context = RunContext()

        with (
            patch.object(
                self.processor,
                "make_stats_object_arguments_for_page",
                return_value=config,
            ),
            patch(
                "integraality.pages_processor.PropertyStatistics",
                side_effect=TypeError("bad params"),
            ),
            self.assertRaises(ConfigException),
        ):
            self.processor.make_stats_object_for_page(
                self._dashboard_page(), run_context=run_context
            )

        self.assertEqual(run_context.sparql_engine, "QLever")

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_record_run_fail_logs_traceback(self, mock_registry_cls):
        # Failures must leave a stack trace in the log, not just the DB one-liner.
        with self.assertLogs("integraality.update", level="ERROR") as cm:
            try:
                raise ValueError("boom")
            except ValueError as exc:
                self.processor._record_run_fail(
                    self._dashboard_page(),
                    trigger_source="WEB",
                    elapsed_time=0.0,
                    exc=exc,
                )

        joined = "\n".join(cm.output)
        self.assertIn("Run failed for Wikidata:Stats", joined)
        self.assertIn("Traceback (most recent call last)", joined)
        self.assertIn("ValueError: boom", joined)

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_record_run_fail_unknown_exception_is_bug(self, mock_registry_cls):
        registry = mock_registry_cls.return_value.__enter__.return_value

        self.processor._record_run_fail(
            self._dashboard_page(),
            trigger_source="CRON",
            elapsed_time=0.1,
            exc=ValueError("boom"),
        )

        _page_meta, run = registry.record_run.call_args[0]
        self.assertEqual(run.error_category, "error")

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_record_run_ok_is_best_effort(self, mock_registry_cls):
        """A recording failure must not propagate (never break the crawl)."""
        registry = mock_registry_cls.return_value.__enter__.return_value
        registry.record_run.side_effect = Exception("db gone")

        # Should not raise.
        self.processor._record_run_ok(
            self._dashboard_page(),
            trigger_source="CRON",
            elapsed_time=1.0,
            stats=self._stats(),
            groupings={},
            report_groupings=[],
            revision_id=1,
        )

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_record_run_ok_records_with_null_revision(self, mock_registry_cls):
        """A local write (LOCAL_WRITE_PATH) or null edit produces no oldid. The
        run still records, with revision_id=None -- OK runs are not required to
        carry a revision."""
        registry = mock_registry_cls.return_value.__enter__.return_value
        self.processor._record_run_ok(
            self._dashboard_page(),
            trigger_source="CRON",
            elapsed_time=1.0,
            stats=self._stats(),
            groupings={},
            report_groupings=[],
            revision_id=None,
        )
        registry.record_run.assert_called_once()
        _page_meta, run = registry.record_run.call_args[0]
        self.assertEqual(run.status, "OK")
        self.assertIsNone(run.revision_id)

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_process_page_records_fail_and_reraises(self, mock_registry_cls):
        """A real dashboard failure inside process_page is recorded as a FAIL
        run and re-raised (guards the try/except wiring, not just the helper)."""
        registry = mock_registry_cls.return_value.__enter__.return_value
        page = self._dashboard_page()
        exc = QueryException("boom", query="SELECT ?x")
        with (
            patch.object(self.processor, "make_stats_object_for_page", side_effect=exc),
            self.assertRaises(QueryException),
        ):
            self.processor.process_page(page, trigger_source="WEB")

        registry.record_run.assert_called_once()
        _page_meta, run = registry.record_run.call_args[0]
        self.assertEqual(run.status, "FAIL")

    @patch("integraality.pages_processor.DashboardRegistry")
    def test_process_page_does_not_record_non_dashboard(self, mock_registry_cls):
        """A page that is not a dashboard (no start template) must not record a
        run or touch the registry -- otherwise arbitrary /update URLs would
        create registry rows for any page."""
        registry = mock_registry_cls.return_value.__enter__.return_value
        page = self._dashboard_page()
        with (
            patch.object(
                self.processor,
                "make_stats_object_for_page",
                side_effect=NoStartTemplateException(),
            ),
            self.assertRaises(NoStartTemplateException),
        ):
            self.processor.process_page(page, trigger_source="WEB")

        registry.record_run.assert_not_called()


class TestProcessOnePage(ProcessortTest):
    """process_one_page classifies transient failures, including those raised
    while lazily constructing the site (login/maxlag)."""

    def test_maxlag_during_site_construction_is_transient(self):
        import pywikibot

        with (
            patch(
                "integraality.pages_processor.pywikibot.Page",
                side_effect=pywikibot.exceptions.MaxlagTimeoutError("maxlag"),
            ),
            self.assertRaises(TransientServerException),
        ):
            self.processor.process_one_page("Some/Dashboard")

    def test_server_error_during_processing_is_transient(self):
        import pywikibot

        with (
            patch("integraality.pages_processor.pywikibot.Page"),
            patch.object(
                self.processor,
                "process_page",
                side_effect=pywikibot.exceptions.ServerError("boom"),
            ),
            self.assertRaises(TransientServerException),
        ):
            self.processor.process_one_page("Some/Dashboard")

    def test_maxlag_in_make_stats_object_for_page_title_is_transient(self):
        import pywikibot

        with (
            patch(
                "integraality.pages_processor.pywikibot.Page",
                side_effect=pywikibot.exceptions.MaxlagTimeoutError("maxlag"),
            ),
            self.assertRaises(TransientServerException),
        ):
            self.processor.make_stats_object_for_page_title("Some/Dashboard")
