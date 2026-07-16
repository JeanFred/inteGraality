"""Server-Sent Events for live update progress."""

import json
import logging
import queue
import threading
import traceback
from logging.handlers import QueueHandler


def _classify_error(e):
    """Build a structured error event dict from an exception."""
    event = {
        "status": "error",
        "error_type": type(e).__name__,
        "error_category": getattr(e, "error_category", "bug"),
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
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    worker_thread = None

    class ThreadFilter(logging.Filter):
        def filter(self, record):
            return record.thread == worker_thread.ident

    thread_filter = ThreadFilter()
    handler.addFilter(thread_filter)

    def target():
        try:
            result = func()
            q.put({"status": "done", "result": result})
        except Exception as e:
            q.put(_classify_error(e))

    worker_thread = threading.Thread(target=target)
    worker_thread.start()

    try:
        while True:
            event = q.get()

            if isinstance(event, logging.LogRecord):
                event = {
                    "status": "progress",
                    "message": event.getMessage(),
                    "level": event.levelname,
                    "phase": getattr(event, "phase", "start"),
                }

            yield f"data: {json.dumps(event)}\n\n"

            if event["status"] in ("done", "error"):
                break
    finally:
        logger.removeHandler(handler)
        worker_thread.join(timeout=1)
