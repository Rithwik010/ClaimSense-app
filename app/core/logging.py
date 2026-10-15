"""Structured JSON logging (INSTRUCTIONS.md §8.9).

Log IDs, routes, durations and versions only. Never log names, addresses, dates of birth or
clinical notes.

Every API request gets a request ID (D-OBS-1): the request middleware binds it to the log context,
so each log line of the request carries it; the response returns it in X-Request-ID; and each
audit event the request writes keeps it (`audit_events.request_id`).
"""

import logging
from uuid import uuid4

import structlog

REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging(level: int = logging.INFO) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    # The request middleware logs every request as JSON; drop uvicorn's duplicate plain-text line.
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger(name)


def bind_request_id() -> str:
    """A new request ID, bound to the log context of the current request (made by the server:
    a client cannot choose the ID its audit events carry)."""
    request_id = uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    return request_id


def current_request_id() -> str | None:
    """The ID of the request being handled, or None outside a request."""
    value = structlog.contextvars.get_contextvars().get("request_id")
    return value if isinstance(value, str) else None


def clear_request_id() -> None:
    structlog.contextvars.clear_contextvars()
