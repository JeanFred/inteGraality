# -*- coding: utf-8  -*-
"""Unit tests for pages_processor.py."""

import argparse
import unittest
from unittest.mock import MagicMock, patch

import fakeredis

from ..pages_processor import (
    ConfigException,
    NoEndTemplateException,
    NoStartTemplateException,
    PagesProcessor,
    main,
)


class ProcessortTest(unittest.TestCase):
    def setUp(self):
        fake_cache_client = fakeredis.FakeStrictRedis()
        self.processor = PagesProcessor(cache_client=fake_cache_client)


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
