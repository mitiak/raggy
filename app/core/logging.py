import logging
import sys
from collections.abc import MutableMapping
from typing import Any, cast

import structlog
from structlog.processors import CallsiteParameter
from structlog.stdlib import BoundLogger


def _normalize_callsite_fields(
    _: Any,
    __: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    filename = event_dict.pop("filename", None)
    function_name = event_dict.pop("func_name", None)
    line_number = event_dict.pop("lineno", None)
    event_dict.setdefault("file", filename)
    event_dict.setdefault("function", function_name)
    event_dict.setdefault("line", line_number)
    return event_dict


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.CallsiteParameterAdder(
                {
                    CallsiteParameter.FILENAME,
                    CallsiteParameter.FUNC_NAME,
                    CallsiteParameter.LINENO,
                }
            ),
            _normalize_callsite_fields,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> BoundLogger:
    return cast(BoundLogger, structlog.get_logger(name))
