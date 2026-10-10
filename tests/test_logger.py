"""Tests for structured JSON logging."""

import json
import logging

from benxautomation.logger import JSONFormatter, get_logger


class TestLogger:
    def test_json_formatter_structure(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Test log message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert "timestamp" in data
        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["message"] == "Test log message"

    def test_get_logger_singleton_handlers(self):
        logger1 = get_logger("my_service")
        logger2 = get_logger("my_service")

        assert logger1 is logger2
        # Check handlers are not duplicated
        assert len(logger1.handlers) == 1
