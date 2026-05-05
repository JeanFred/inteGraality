import json
import logging
import queue
import threading
import traceback
from logging.handlers import QueueHandler


def run_with_sse(func, logger_name="integraality.update"):
    """Run func in a background thread, yielding SSE events from its log messages."""
    q = queue.Queue()
    logger = logging.getLogger(logger_name)
    handler = QueueHandler(q)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    def target():
        try:
            result = func()
            q.put({"status": "done", "result": result})
        except Exception as e:
            q.put(
                {
                    "status": "error",
                    "message": str(e),
                    "traceback": traceback.format_exception(
                        type(e), e, e.__traceback__
                    ),
                }
            )

    thread = threading.Thread(target=target)
    thread.start()

    try:
        while True:
            event = q.get()

            if isinstance(event, logging.LogRecord):
                event = {
                    "status": "progress",
                    "message": event.getMessage(),
                    "level": event.levelname,
                }

            yield f"data: {json.dumps(event)}\n\n"

            if event["status"] in ("done", "error"):
                break
    finally:
        logger.removeHandler(handler)
        thread.join(timeout=1)
