# -*- coding: utf-8  -*-
import unittest

from app import app


class AppTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.app = app.test_client()

    def test_index_page(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn("<h1>InteGraality</h1>", response.get_data(as_text=True))
