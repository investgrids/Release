"""
Structlog configuration — call configure_logging() once at application startup.
All loggers in the application should use structlog.get_logger(), not logging.getLogger().
Standard-library log records are captured and routed through structlog processors.
"""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """
    Set up structlog with shared processors.

    Args:
        level:     Log level string ("DEBUG", "INFO", "WARNING", "ERROR")
        json_logs: True → JSON output (production); False → coloured console (dev)
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # Runs only on records that did NOT originate from structlog (stdlib
        # `logging.getLogger()` calls from APScheduler, uvicorn, etc). Must
        # run before remove_processors_meta strips "_record" — add_logger_name
        # needs it to resolve the logger name for these foreign records.
        foreign_pre_chain=shared_processors,
        # Runs on every record regardless of origin.
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Silence noisy third-party loggers
    for name in ("uvicorn.access", "httpx", "httpcore", "yfinance", "peewee"):
        logging.getLogger(name).setLevel(logging.WARNING)
