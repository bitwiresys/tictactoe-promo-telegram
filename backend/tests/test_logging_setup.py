from __future__ import annotations

import json
import logging
import sys

from app.logging_setup import (
    JsonLogFormatter,
    RequestIdFilter,
    configure_logging,
    get_request_id,
    log_event,
    set_request_id,
)


def test_get_request_id_generates_and_is_stable() -> None:
    set_request_id("")
    rid1 = get_request_id()
    rid2 = get_request_id()
    assert rid1
    assert rid1 == rid2


def test_request_id_filter_sets_record_attr() -> None:
    set_request_id("rid")
    f = RequestIdFilter()
    record = logging.LogRecord(
        name="x",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    assert f.filter(record) is True
    assert record.request_id == "rid"


def test_json_log_formatter_includes_fields() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="x",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.request_id = "rid"
    record.event = "my_event"
    record.extra_field = "v"

    out = formatter.format(record)
    payload = json.loads(out)
    assert payload["level"] == "info"
    assert payload["logger"] == "x"
    assert payload["message"] == "hello"
    assert payload["request_id"] == "rid"
    assert payload["event"] == "my_event"
    assert payload["extra_field"] == "v"


def test_json_log_formatter_includes_exc_info() -> None:
    formatter = JsonLogFormatter()
    try:
        zero = 0
        _ = 1 / zero
    except ZeroDivisionError:
        exc = sys.exc_info()

    record = logging.LogRecord(
        name="x",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="boom",
        args=(),
        exc_info=exc,
    )
    record.request_id = "rid"

    payload = json.loads(formatter.format(record))
    assert "exc_info" in payload


def test_configure_logging_sets_root_handler_and_uvicorn_access() -> None:
    configure_logging("info")
    root = logging.getLogger()
    assert root.handlers
    assert isinstance(root.handlers[0].formatter, JsonLogFormatter)

    uvicorn_access = logging.getLogger("uvicorn.access")
    assert uvicorn_access.propagate is True


def test_log_event_sets_extra_fields() -> None:
    class _Capture(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            self.records: list[logging.LogRecord] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.records.append(record)

    logger = logging.getLogger("test_capture")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = _Capture()
    logger.handlers.clear()
    logger.addHandler(handler)

    log_event(logger, "evt", a=1)
    assert len(handler.records) == 1
    rec = handler.records[0]
    assert rec.event == "evt"
    assert rec.a == 1
