import json
import logging
import unittest

from ..sse import run_with_sse


class RunWithSSETest(unittest.TestCase):
    def test_success(self):
        def func():
            logger = logging.getLogger("integraality.update")
            logger.info("step 1")
            logger.info("step 2")
            return 42.0

        events = list(run_with_sse(func))
        parsed = [
            json.loads(e.removeprefix("data: "))
            for e in events
            if e.startswith("data:")
        ]
        messages = [e["message"] for e in parsed if e["status"] == "progress"]
        self.assertIn("step 1", messages)
        self.assertIn("step 2", messages)
        done = [e for e in parsed if e["status"] == "done"]
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0]["result"], 42.0)

    def test_error(self):
        def func():
            raise ValueError("boom")

        events = list(run_with_sse(func))
        parsed = [
            json.loads(e.removeprefix("data: "))
            for e in events
            if e.startswith("data:")
        ]
        errors = [e for e in parsed if e["status"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("boom", errors[0]["message"])

    def test_error_includes_error_type(self):
        def func():
            raise RuntimeError("unexpected")

        events = list(run_with_sse(func))
        parsed = [
            json.loads(e.removeprefix("data: "))
            for e in events
            if e.startswith("data:")
        ]
        error = [e for e in parsed if e["status"] == "error"][0]
        self.assertEqual(error["error_type"], "RuntimeError")
        self.assertEqual(error["error_category"], "bug")
        self.assertIn("traceback", error)

    def test_error_query_exception(self):
        from ..sparql_utils import QueryException

        def func():
            raise QueryException("Timeout", "SELECT ?x WHERE {}")

        events = list(run_with_sse(func))
        parsed = [
            json.loads(e.removeprefix("data: "))
            for e in events
            if e.startswith("data:")
        ]
        error = [e for e in parsed if e["status"] == "error"][0]
        self.assertEqual(error["error_type"], "QueryException")
        self.assertEqual(error["error_category"], "query")
        self.assertEqual(error["query"], "SELECT ?x WHERE {}")
        self.assertIn("Timeout", error["message"])

    def test_error_processing_exception(self):
        from ..pages_processor import ProcessingException

        def func():
            raise ProcessingException("Bad config")

        events = list(run_with_sse(func))
        parsed = [
            json.loads(e.removeprefix("data: "))
            for e in events
            if e.startswith("data:")
        ]
        error = [e for e in parsed if e["status"] == "error"][0]
        self.assertEqual(error["error_type"], "ProcessingException")
        self.assertEqual(error["error_category"], "config")
        self.assertIn("Bad config", error["message"])

    def test_error_transient_server_exception(self):
        from ..pages_processor import TransientServerException

        def func():
            raise TransientServerException("503")

        events = list(run_with_sse(func))
        parsed = [
            json.loads(e.removeprefix("data: "))
            for e in events
            if e.startswith("data:")
        ]
        error = [e for e in parsed if e["status"] == "error"][0]
        self.assertEqual(error["error_type"], "TransientServerException")
        self.assertEqual(error["error_category"], "transient")
        self.assertIn("503", error["message"])

    def test_error_category_for_subclass(self):
        from ..pages_processor import ConfigException

        def func():
            raise ConfigException("missing property")

        events = list(run_with_sse(func))
        parsed = [
            json.loads(e.removeprefix("data: "))
            for e in events
            if e.startswith("data:")
        ]
        error = [e for e in parsed if e["status"] == "error"][0]
        self.assertEqual(error["error_type"], "ConfigException")
        self.assertEqual(error["error_category"], "config")

    def test_progress_with_query_extra(self):
        def func():
            logger = logging.getLogger("integraality.update")
            logger.info("Querying P569...", extra={"query": "SELECT ?x WHERE {}"})
            return 1.0

        events = list(run_with_sse(func))
        parsed = [
            json.loads(e.removeprefix("data: "))
            for e in events
            if e.startswith("data:")
        ]
        progress = [e for e in parsed if e["status"] == "progress"]
        self.assertEqual(len(progress), 1)
        self.assertEqual(progress[0]["query"], "SELECT ?x WHERE {}")
        self.assertIn("P569", progress[0]["message"])

    def test_progress_without_query_extra(self):
        def func():
            logger = logging.getLogger("integraality.update")
            logger.info("Saving to wiki...")
            return 1.0

        events = list(run_with_sse(func))
        parsed = [
            json.loads(e.removeprefix("data: "))
            for e in events
            if e.startswith("data:")
        ]
        progress = [e for e in parsed if e["status"] == "progress"]
        self.assertEqual(len(progress), 1)
        self.assertIsNone(progress[0]["query"])
