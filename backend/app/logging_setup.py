from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def set_request_id(value: str) -> None:
    _request_id_ctx.set(value)


def get_request_id() -> str:
    value = _request_id_ctx.get()
    if value:
        return value
    generated = str(uuid.uuid4())
    _request_id_ctx.set(generated)
    return generated


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", ""),
        }

        event = getattr(record, "event", None)
        if isinstance(event, str) and event:
            payload["event"] = event

        for k, v in record.__dict__.items():
            if k in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "request_id",
                "stack_info",
                "thread",
                "threadName",
            }:
                continue
            if k not in payload:
                payload[k] = v

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(RequestIdFilter())

    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = True


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(event, extra={"event": event, **fields})
