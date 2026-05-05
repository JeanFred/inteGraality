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
