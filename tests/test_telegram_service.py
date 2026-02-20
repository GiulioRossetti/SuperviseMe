import sys
import os
from unittest.mock import MagicMock, patch

# Define mocks
mocks = {}
mocks['flask'] = MagicMock()
mocks['flask_sqlalchemy'] = MagicMock()
mocks['flask_login'] = MagicMock()
mocks['flask_mail'] = MagicMock()
mocks['flask_wtf'] = MagicMock()
mocks['flask_wtf.csrf'] = MagicMock()
mocks['markdown'] = MagicMock()
mocks['flask_moment'] = MagicMock()
mocks['werkzeug'] = MagicMock()
mocks['werkzeug.security'] = MagicMock()
mocks['sqlalchemy'] = MagicMock()
mocks['flask_migrate'] = MagicMock()
mocks['authlib.integrations.flask_client'] = MagicMock()
mocks['telebot'] = MagicMock()
mocks['telebot.apihelper'] = MagicMock()

# Mock superviseme and its components
mock_db = MagicMock()
mock_models = MagicMock()

# Ensure models have necessary attributes
mock_models.TelegramBotConfig = MagicMock()
mock_models.User_mgmt = MagicMock()

mocks['superviseme.db'] = mock_db
mocks['superviseme.models'] = mock_models

# Expose key mocks for test configuration
mock_flask = mocks['flask']

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Patch sys.modules to mock dependencies during import
with patch.dict(sys.modules, mocks):
    from superviseme.utils.telegram_service import TelegramService

def test_format_message_basic():
    """Test basic message formatting with title and message"""
    service = TelegramService()
    title = "Test Title"
    message = "Test Message"

    expected = "<b>🔔 Test Title</b>\n\nTest Message\n\n<i>📚 SuperviseMe</i>"
    assert service._format_message(title, message) == expected

def test_format_message_with_absolute_url():
    """Test message formatting with an absolute URL"""
    service = TelegramService()
    title = "Test Title"
    message = "Test Message"
    url = "https://example.com"

    expected = "<b>🔔 Test Title</b>\n\nTest Message\n\n<a href='https://example.com'>🔗 View Details</a>\n\n<i>📚 SuperviseMe</i>"
    assert service._format_message(title, message, action_url=url) == expected

def test_format_message_with_relative_url():
    """Test message formatting with a relative URL, using current_app config"""
    service = TelegramService()
    title = "Test Title"
    message = "Test Message"
    url = "/some/path"

    # Mock current_app configuration
    mock_flask.current_app.config.get.return_value = "https://mysite.com"

    expected = "<b>🔔 Test Title</b>\n\nTest Message\n\n<a href='https://mysite.com/some/path'>🔗 View Details</a>\n\n<i>📚 SuperviseMe</i>"
    assert service._format_message(title, message, action_url=url) == expected

    # Verify config was accessed correctly
    mock_flask.current_app.config.get.assert_called_with('BASE_URL', 'https://superviseme.local')

def test_format_message_with_hash_url():
    """Test that '#' URL is ignored"""
    service = TelegramService()
    title = "Test Title"
    message = "Test Message"
    url = "#"

    expected = "<b>🔔 Test Title</b>\n\nTest Message\n\n<i>📚 SuperviseMe</i>"
    assert service._format_message(title, message, action_url=url) == expected

def test_format_message_with_empty_url():
    """Test that empty URL is ignored"""
    service = TelegramService()
    title = "Test Title"
    message = "Test Message"
    url = ""

    expected = "<b>🔔 Test Title</b>\n\nTest Message\n\n<i>📚 SuperviseMe</i>"
    assert service._format_message(title, message, action_url=url) == expected

def test_format_message_with_none_url():
    """Test that None URL is ignored"""
    service = TelegramService()
    title = "Test Title"
    message = "Test Message"
    url = None

    expected = "<b>🔔 Test Title</b>\n\nTest Message\n\n<i>📚 SuperviseMe</i>"
    assert service._format_message(title, message, action_url=url) == expected
