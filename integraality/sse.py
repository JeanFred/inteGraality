"""Server-Sent Events for live update progress."""

import json
import logging
import queue
import threading
import traceback
from logging.handlers import QueueHandler

from .error_category import ErrorCategory


def _classify_error(e):
    """Build a structured error event dict from an exception."""
    event = {
        "status": "error",
        "error_type": type(e).__name__,
        "error_category": getattr(e, "error_category", ErrorCategory.ERROR),
        "message": str(e),
        "traceback": traceback.format_exception(type(e), e, e.__traceback__),
    }

    if hasattr(e, "query"):
        event["query"] = e.query

    return event


def run_with_sse(func, logger_name="integraality.update"):
    """Run func in a background thread, yielding SSE events from its log messages."""
    q = queue.Queue()
    logger = logging.getLogger(logger_name)
    handler = QueueHandler(q)
    handler.setLevel(logging.INFO)

    worker_thread = None

    class ThreadFilter(logging.Filter):
        def filter(self, record):
            return record.thread == worker_thread.ident

    handler.addFilter(ThreadFilter())

    def target():
        try:
            result = func()
            q.put({"status": "done", "result": result})
        except Exception as e:
            q.put(_classify_error(e))

    # Inside the try so the finally always detaches the handler.
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        worker_thread = threading.Thread(target=target)
        worker_thread.start()

        while True:
            event = q.get()

            if isinstance(event, logging.LogRecord):
                event = {
                    "status": "progress",
                    "message": event.getMessage(),
                    "level": event.levelname,
                    "phase": getattr(event, "phase", "start"),
                    "query": getattr(event, "query", None),
                    "step_key": getattr(event, "step_key", None),
                }

            yield f"data: {json.dumps(event)}\n\n"

            if event["status"] in ("done", "error"):
                break
    finally:
        logger.removeHandler(handler)
        if worker_thread is not None:
            worker_thread.join(timeout=1)
