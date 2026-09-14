"""Error categories for SSE error reporting."""

import enum


class ErrorCategory(str, enum.Enum):
    """Stable categories the JS client branches on for error display."""

    QUERY = "query"
    TIMEOUT = "timeout"
    TRANSIENT = "transient"
    CONFIG = "config"
    # Neutral fallback for a failure whose cause we haven't classified. Not a
    # claim that inteGraality is at fault -- just "an error, cause unknown".
    ERROR = "error"
