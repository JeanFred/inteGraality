# -*- coding: utf-8  -*-
import unittest
from unittest.mock import patch

from app import app
from pages_processor import ProcessingException


class AppTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.app = app.test_client()


class BasicTests(AppTests):

    def test_index_page(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn("<h1>InteGraality</h1>", response.get_data(as_text=True))

    def test_404_page(self):
        response = self.app.get('/unexisting_page')
        self.assertEqual(response.status_code, 404)
        self.assertIn("This page does not exist.", response.get_data(as_text=True))


class UpdateTests(AppTests):

    def setUp(self):
        super().setUp()
        patcher = patch('app.PagesProcessor', autospec=True)
        self.mock_pages_processor = patcher.start()
        self.addCleanup(patcher.stop)
        self.page_title = 'Foo'
        self.linked_page = '<a href="https://wikidata.org/wiki/{page}">{page}</a>'.format(page=self.page_title)

    def assertSuccessPage(self, response, message):
        """A custom assertion for a success page."""
        self.assertEqual(response.status_code, 200)
        contents = response.get_data(as_text=True)
        self.assertIn("alert-success", contents)
        self.assertIn(message, contents)

    def assertErrorPage(self, response, message):
        """A custom assertion for an error page."""
        self.assertEqual(response.status_code, 200)
        contents = response.get_data(as_text=True)
        self.assertIn("alert-danger", contents)
        self.assertIn(message, contents)

    def test_update_success(self):
        response = self.app.get('/update?page=%s' % self.page_title)
        self.mock_pages_processor.assert_called_once_with()
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(page_title=self.page_title)
        self.assertSuccessPage(response, 'Updated page ')

    def test_update_error_processing_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = ProcessingException
        response = self.app.get('/update?page=%s' % self.page_title)
        self.mock_pages_processor.assert_called_once_with()
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(page_title=self.page_title)
        message = '<p>Something went wrong when updating page {page}. Please check your configuration.</p>'.format(page=self.linked_page)  # noqa
        self.assertErrorPage(response, message)

    def test_update_error_unknown_exception(self):
        self.mock_pages_processor.return_value.process_one_page.side_effect = ValueError
        response = self.app.get('/update?page=%s' % self.page_title)
        self.mock_pages_processor.assert_called_once_with()
        self.mock_pages_processor.return_value.process_one_page.assert_called_once_with(page_title=self.page_title)
        message = '<p>Something catastrophic happened when processing page {page}.</p>'.format(page=self.linked_page)
        self.assertErrorPage(response, message)
