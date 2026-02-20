import sys
import os
import json
import logging
from unittest.mock import MagicMock

# Mock external dependencies before they are imported by the application code
mock_flask = MagicMock()
mock_login = MagicMock()
# mock_sqlalchemy = MagicMock() # Not used in logging_config.py directly

sys.modules['flask'] = mock_flask
sys.modules['flask_login'] = mock_login
# sys.modules['flask_sqlalchemy'] = mock_sqlalchemy

# Now import the functions to test
# We import directly from the file location to avoid triggering superviseme/__init__.py
utils_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../superviseme/utils'))
sys.path.insert(0, utils_path)

from logging_config import JSONFormatter  # noqa: E402

def test_json_formatter_basic():
    """Test basic JSON formatting"""
    formatter = JSONFormatter()

    # Create a LogRecord
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
        func="test_func"
    )

    formatted_output = formatter.format(record)
    log_entry = json.loads(formatted_output)

    assert log_entry['logger'] == "test_logger"
    assert log_entry['level'] == "INFO"
    assert log_entry['message'] == "Test message"
    assert log_entry['function'] == "test_func"
    assert log_entry['line'] == 10
    assert 'timestamp' in log_entry

def test_json_formatter_with_exception():
    """Test JSON formatting with exception info"""
    formatter = JSONFormatter()

    try:
        raise ValueError("Test exception")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname=__file__,
        lineno=20,
        msg="Error occurred",
        args=(),
        exc_info=exc_info,
        func="test_func"
    )

    formatted_output = formatter.format(record)
    log_entry = json.loads(formatted_output)

    assert log_entry['message'] == "Error occurred"
    assert 'exception' in log_entry
    assert "ValueError: Test exception" in log_entry['exception']

def test_json_formatter_extra_fields():
    """Test JSON formatting with extra fields"""
    formatter = JSONFormatter()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=30,
        msg="User action",
        args=(),
        exc_info=None,
        func="test_func"
    )

    # Add extra fields like `logging.Logger.info(..., extra={'user_id': 123})` does
    record.user_id = 123
    record.action_type = "login"

    formatted_output = formatter.format(record)
    log_entry = json.loads(formatted_output)

    assert log_entry['user_id'] == 123
    assert log_entry['action_type'] == "login"
    assert log_entry['message'] == "User action"

def test_json_formatter_ignored_fields():
    """Test that standard LogRecord attributes are not duplicated in JSON output"""
    formatter = JSONFormatter()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=40,
        msg="Test ignored fields",
        args=(),
        exc_info=None,
        func="test_func"
    )

    # These fields are standard attributes of LogRecord, they should be mapped or ignored,
    # but not appear as extra keys in the JSON root unless explicitly mapped.
    # The JSONFormatter implementation maps some of them (e.g., 'name' -> 'logger', 'levelname' -> 'level').
    # But attributes like 'filename', 'module', 'threadName' are often present in LogRecord.

    formatted_output = formatter.format(record)
    log_entry = json.loads(formatted_output)

    # 'name' is mapped to 'logger', so 'name' should not be present as a key
    assert 'name' not in log_entry
    assert 'logger' in log_entry

    # 'msg' is mapped to 'message'
    assert 'msg' not in log_entry
    assert 'message' in log_entry

    # 'levelname' is mapped to 'level'
    assert 'levelname' not in log_entry
    assert 'level' in log_entry

    # 'args' should be ignored
    assert 'args' not in log_entry
