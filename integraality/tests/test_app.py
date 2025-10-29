# -*- coding: utf-8  -*-
import unittest
from unittest.mock import patch

import column
from app import app
from pages_processor import ProcessingException
from sparql_utils import QueryException


class AppTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.app = app.test_client()


class BasicTests(AppTests):
    def test_index_page(self):
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("<h1>InteGraality</h1>", response.get_data(as_text=True))

    def test_404_page(self):
        response = self.app.get("/unexisting_page")
        self.assertEqual(response.status_code, 404)
        self.assertIn("This page does not exist.", response.get_data(as_text=True))


class PagesProcessorTests(AppTests):
    def setUp(self):
        super().setUp()
        patcher = patch("app.PagesProcessor", autospec=True)
        self.mock_pages_processor = patcher.start()
        self.addCleanup(patcher.stop)
        self.page_title = "Foo"
        self.page_url = "https://wikidata.org/wiki/%s" % self.page_title
        self.linked_page = '<a href="%s">%s</a>' % (self.page_url, self.page_title)

    def assertSuccessPage(self, response, message):
        """A custom assertion for a success page."""
        self.assertEqual(response.status_code, 200)
        contents = response.get_data(as_text=True)
        self.assertIn("alert-success", contents)
        self.assertPresent(message, contents)

    def assertErrorPage(self, response, message):
        """A custom assertion for an error page."""
        self.assertEqual(response.status_code, 200)
        contents = response.get_data(as_text=True)
        self.assertIn("alert-danger", contents)
        self.assertPresent(message, contents)

    def assertPresent(self, message, response):
        self.assertIn(
            message.replace(" ", "").replace("\t", "").replace("\n", ""),
            response.replace(" ", "").replace("\t", "").replace("\n", ""),
        )


class UpdateTests(PagesProcessorTests):
    def test_update_success(self):
        response = self.app.get(
            "/update?page=%s&url=%s" % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(
            page_title=self.page_title
        )
        message = "Updated page {page}".format(page=self.linked_page)
        self.assertSuccessPage(response, message)

    def test_update_error_processing_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = (
            ProcessingException
        )
        response = self.app.get(
            "/update?page=%s&url=%s" % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(
            page_title=self.page_title
        )
        message = "<p>Something went wrong when updating page {page}. Please check your configuration.</p>".format(
            page=self.linked_page
        )  # noqa
        self.assertErrorPage(response, message)

    def test_update_error_unknown_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = ValueError
        response = self.app.get(
            "/update?page=%s&url=%s" % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(
            page_title=self.page_title
        )
        message = "<p>Something catastrophic happened when processing page {page}.</p>".format(
            page=self.linked_page
        )
        self.assertErrorPage(response, message)

    def test_update_error_query_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = (
            QueryException("Error", "SELECT X")
        )
        response = self.app.get(
            "/update?page=%s&url=%s" % (self.page_title, self.page_url)
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
        self.assertErrorPage(response, expected)
        buttons = (
            '<a class="btn btn-primary" href="https://query.wikidata.org/#SELECT X">Try it in Wikidata Query Service</a>'
            '<a class="btn btn-info" href="https://qlever.dev/wikidata/?query='
        )
        self.assertErrorPage(response, buttons)

    def test_update_success_meta(self):
        page_url = "https://meta.wikimedia.org/wiki/%s" % self.page_title
        response = self.app.get("/update?page=%s&url=%s" % (self.page_title, page_url))
        self.mock_pages_processor.assert_called_once_with(page_url)
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(
            page_title=self.page_title
        )
        message = 'Updated page <a href="%s">%s</a>' % (page_url, self.page_title)
        self.assertSuccessPage(response, message)


class QueriesTests(PagesProcessorTests):
    def setUp(self):
        super().setUp()
        self.column_P1 = column.PropertyColumn(property="P1")
        self.column_Lbr = column.LabelColumn(language="br")
        self.column_Dbr = column.DescriptionColumn(language="br")

        patcher04 = patch("grouping.ItemGroupingConfiguration", autospec=True)
        self.mock_grouping_configuration = patcher04.start()
        self.addCleanup(patcher04.stop)
        self.mock_grouping_configuration.format_predicate_html.return_value = (
            '<a href="https://wikidata.org/wiki/Property:P495">P495</a>'
        )
        self.mock_grouping_configuration.property = "P495"

        patcher1 = patch("pages_processor.PropertyStatistics", autospec=True)
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

    def test_queries_success(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.return_value = "X"
        self.mock_property_statistics.get_query_for_items_for_property_negative.return_value = "Z"
        self.mock_property_statistics.GROUP_MAPPING.side_effect = ValueError
        self.mock_property_statistics.GROUP_MAPPING.__members__.get.return_value = "Q2"
        response = self.app.get(
            "/queries?page=%s&url=%s&column=P1&grouping=Q2"
            % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.assert_called_once_with(
            self.column_P1, "Q2"
        )
        self.mock_property_statistics.get_query_for_items_for_property_negative.assert_called_once_with(
            self.column_P1, "Q2"
        )
        expected = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            '<a href="https://wikidata.org/wiki/Property:P1">P1</a>, '
            'with <a href="https://wikidata.org/wiki/Q2">Q2</a> as <a href="https://wikidata.org/wiki/Property:P495">P495</a>.</p>\n\t'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">All items with the property set</a>\n\t'  # noqa
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">All items without the property set</a>'  # noqa
        )
        self.assertEqual(response.status_code, 200)
        self.assertPresent(expected, response.get_data(as_text=True))

    def test_queries_success_no_grouping(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.return_value = "X"
        self.mock_property_statistics.get_query_for_items_for_property_negative.return_value = "Z"
        self.mock_property_statistics.GROUP_MAPPING.return_value = "No"
        response = self.app.get(
            "/queries?page=%s&url=%s&column=P1&grouping=None"
            % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.assert_called_once_with(
            self.column_P1, "No"
        )
        self.mock_property_statistics.get_query_for_items_for_property_negative.assert_called_once_with(
            self.column_P1, "No"
        )
        expected = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            '<a href="https://wikidata.org/wiki/Property:P1">P1</a>, '
            'without <a href="https://wikidata.org/wiki/Property:P495">P495</a> grouping.</p>\n\t'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">All items with the property set</a>\n\t'  # noqa
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">All items without the property set</a>'  # noqa
        )
        self.assertEqual(response.status_code, 200)
        self.assertPresent(expected, response.get_data(as_text=True))

    def test_queries_success_labels(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.return_value = "X"
        self.mock_property_statistics.get_query_for_items_for_property_negative.return_value = "Z"
        self.mock_property_statistics.GROUP_MAPPING.side_effect = ValueError
        self.mock_property_statistics.GROUP_MAPPING.__members__.get.return_value = "Q2"
        response = self.app.get(
            "/queries?page=%s&url=%s&column=Lbr&grouping=Q2"
            % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.assert_called_once_with(
            self.column_Lbr, "Q2"
        )
        self.mock_property_statistics.get_query_for_items_for_property_negative.assert_called_once_with(
            self.column_Lbr, "Q2"
        )
        expected = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            "br label, "
            'with <a href="https://wikidata.org/wiki/Q2">Q2</a> as <a href="https://wikidata.org/wiki/Property:P495">P495</a>.</p>\n\t'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">All items with the label set</a>\n\t'  # noqa
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">All items without the label set</a>'  # noqa
        )
        self.assertEqual(response.status_code, 200)
        self.assertPresent(expected, response.get_data(as_text=True))

    def test_queries_success_descriptions(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.return_value = "X"
        self.mock_property_statistics.get_query_for_items_for_property_negative.return_value = "Z"
        self.mock_property_statistics.GROUP_MAPPING.side_effect = ValueError
        self.mock_property_statistics.GROUP_MAPPING.__members__.get.return_value = "Q2"
        response = self.app.get(
            "/queries?page=%s&url=%s&column=Dbr&grouping=Q2"
            % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.assert_called_once_with(
            self.column_Dbr, "Q2"
        )
        self.mock_property_statistics.get_query_for_items_for_property_negative.assert_called_once_with(
            self.column_Dbr, "Q2"
        )
        expected = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            "br description, "
            'with <a href="https://wikidata.org/wiki/Q2">Q2</a> as <a href="https://wikidata.org/wiki/Property:P495">P495</a>.</p>\n\t'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">All items with the description set</a>\n\t'  # noqa
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">All items without the description set</a>'  # noqa
        )
        self.assertEqual(response.status_code, 200)
        self.assertPresent(expected, response.get_data(as_text=True))

    def test_queries_success_totals(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.return_value = "X"
        self.mock_property_statistics.get_query_for_items_for_property_negative.return_value = "Z"
        self.mock_property_statistics.GROUP_MAPPING.return_value = "Totals"
        response = self.app.get(
            "/queries?page=%s&url=%s&property=P1&grouping="
            % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.assert_called_once_with(
            self.column_P1, "Totals"
        )
        self.mock_property_statistics.get_query_for_items_for_property_negative.assert_called_once_with(
            self.column_P1, "Totals"
        )
        expected = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            '<a href="https://wikidata.org/wiki/Property:P1">P1</a>, '
            "for the totals.</p>\n\t"
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">All items with the property set</a>\n\t'  # noqa
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">All items without the property set</a>'  # noqa
        )
        self.assertEqual(response.status_code, 200)
        self.assertPresent(expected, response.get_data(as_text=True))

    def test_queries_error_processing_exception(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.side_effect = ProcessingException
        response = self.app.get(
            "/queries?page=%s&url=%s&property=P1&grouping=Q2"
            % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )  # noqa
        message = "<p>Something went wrong when generating queries from page {page}.</p>".format(
            page=self.linked_page
        )
        self.assertErrorPage(response, message)

    def test_queries_error_unknown_exception(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.side_effect = ValueError
        response = self.app.get(
            "/queries?page=%s&url=%s&property=P1&grouping=Q2"
            % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )  # noqa
        message = "<p>Something catastrophic happened when generating queries from page {page}.</p>".format(
            page=self.linked_page
        )  # noqa
        self.assertErrorPage(response, message)

    def test_queries_success_unknown_value_grouping(self):
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.return_value = self.mock_property_statistics  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.return_value = "X"
        self.mock_property_statistics.get_query_for_items_for_property_negative.return_value = "Z"
        self.mock_property_statistics.GROUP_MAPPING.side_effect = ValueError
        self.mock_property_statistics.GROUP_MAPPING.__members__.get.return_value = (
            "UNKNOWN_VALUE"
        )
        response = self.app.get(
            "/queries?page=%s&url=%s&column=P1&grouping=UNKNOWN_VALUE"
            % (self.page_title, self.page_url)
        )
        self.mock_pages_processor.assert_called_once_with(self.page_url)
        self.mock_pages_processor.return_value.make_stats_object_for_page_title.assert_called_once_with(
            page_title=self.page_title
        )  # noqa
        self.mock_property_statistics.get_query_for_items_for_property_positive.assert_called_once_with(
            self.column_P1, "UNKNOWN_VALUE"
        )
        self.mock_property_statistics.get_query_for_items_for_property_negative.assert_called_once_with(
            self.column_P1, "UNKNOWN_VALUE"
        )
        expected = (
            '<p>From page <a href="https://wikidata.org/wiki/Foo">Foo</a>, '
            '<a href="https://wikidata.org/wiki/Property:P1">P1</a>, '
            'with unknown value as <a href="https://wikidata.org/wiki/Property:P495">P495</a>.</p>\n\t'
            '<a class="btn btn-primary" href="https://query.wikidata.org/#X" role="button">All items with the property set</a>\n\t'  # noqa
            '<a class="btn btn-primary" href="https://query.wikidata.org/#Z" role="button">All items without the property set</a>'  # noqa
        )
        self.assertEqual(response.status_code, 200)
        self.assertPresent(expected, response.get_data(as_text=True))
