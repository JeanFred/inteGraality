"""Error categories for SSE error reporting."""

import enum


class ErrorCategory(str, enum.Enum):
    """Stable categories the JS client branches on for error display."""

    QUERY = "query"
    TRANSIENT = "transient"
    CONFIG = "config"
