import sys
import os
from unittest.mock import MagicMock, patch

# Mock external dependencies before they are imported by the application code
mock_flask = MagicMock()
mock_sqlalchemy = MagicMock()
mock_login = MagicMock()
mock_mail = MagicMock()
mock_wtf = MagicMock()
mock_markdown = MagicMock()
mock_moment = MagicMock()
mock_werkzeug = MagicMock()

sys.modules['flask'] = mock_flask
sys.modules['flask_sqlalchemy'] = mock_sqlalchemy
sys.modules['flask_login'] = mock_login
sys.modules['flask_mail'] = mock_mail
sys.modules['flask_wtf'] = mock_wtf
sys.modules['flask_wtf.csrf'] = MagicMock()
sys.modules['markdown'] = mock_markdown
sys.modules['flask_moment'] = mock_moment
sys.modules['werkzeug'] = mock_werkzeug
sys.modules['werkzeug.security'] = MagicMock()
sys.modules['sqlalchemy'] = MagicMock()

# Mock superviseme and its components
mock_db = MagicMock()
mock_models = MagicMock()

sys.modules['superviseme.db'] = mock_db
sys.modules['superviseme.models'] = mock_models

# Now import the functions to test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from superviseme.utils.todo_parser import parse_todo_references, format_text_with_todo_links  # noqa: E402


def test_parse_todo_ids():
    """Test extraction of numeric IDs"""
    # Test @todo:ID format
    assert parse_todo_references("Check @todo:1") == [1]
    # Test #todo-ID format
    assert parse_todo_references("Check #todo-2") == [2]
    # Test multiple IDs
    result = parse_todo_references("@todo:1 and #todo-2")
    assert sorted(result) == [1, 2]
    # Test case insensitivity
    assert parse_todo_references("@TODO:3") == [3]
    assert parse_todo_references("#TODO-4") == [4]

def test_parse_todo_titles():
    """Test extraction of todo references by title"""
    mock_todo1 = MagicMock()
    mock_todo1.id = 10
    mock_todo1.title = "Literature Review"

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.filter.return_value.all.return_value = [mock_todo1]

        assert parse_todo_references('@todo:"Literature Review"') == [10]
        MockTodo.title.ilike.assert_called_with('%Literature Review%')

def test_parse_todo_slugs():
    """Test extraction of todo references by slug"""
    mock_todo = MagicMock()
    mock_todo.id = 30

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.filter.return_value.all.return_value = [mock_todo]
        assert parse_todo_references("@todo:my-task") == [30]
        MockTodo.title.ilike.assert_called_with('%my task%')

def test_parse_mixed_references():
    """Test mixed ID and title references"""
    mock_todo = MagicMock()
    mock_todo.id = 100

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.filter.return_value.all.return_value = [mock_todo]
        result = parse_todo_references("Finish @todo:1 and start @todo:project-plan")
        assert sorted(result) == [1, 100]

def test_parse_duplicates():
    """Test that duplicate references are removed"""
    assert parse_todo_references("@todo:1 and @todo:1") == [1]

    mock_todo = MagicMock()
    mock_todo.id = 1
    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.filter.return_value.all.return_value = [mock_todo]
        result = parse_todo_references("@todo:1 and @todo:\"Title of 1\"")
        assert result == [1]

def test_parse_no_matches():
    """Test when no references are present"""
    assert parse_todo_references("Just some regular text") == []
    assert parse_todo_references("") == []

def test_parse_multiple_title_matches():
    """Test when one title search returns multiple todos"""
    mock_todo1 = MagicMock()
    mock_todo1.id = 40
    mock_todo2 = MagicMock()
    mock_todo2.id = 41

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.filter.return_value.all.return_value = [mock_todo1, mock_todo2]

        result = parse_todo_references("@todo:search-term")
        assert sorted(result) == [40, 41]

def test_format_text_with_todo_links():
    """Test formatting text with todo links"""
    mock_todo = MagicMock()
    mock_todo.id = 1
    mock_todo.title = "Test Todo"

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.get.return_value = mock_todo

        text = "Please check @todo:1"
        formatted = format_text_with_todo_links(text)
        assert '<a href="/supervisor/todo/1"' in formatted
        assert 'title="Test Todo"' in formatted
        assert '@todo:1</a>' in formatted

def test_format_text_with_hash_todo_links():
    """Test formatting text with #todo-ID links"""
    mock_todo = MagicMock()
    mock_todo.id = 2
    mock_todo.title = "Hash Todo"

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.get.return_value = mock_todo

        text = "Please check #todo-2"
        formatted = format_text_with_todo_links(text)
        assert '<a href="/supervisor/todo/2"' in formatted
        assert '#todo-2</a>' in formatted

def test_format_text_invalid_todo():
    """Test formatting text when todo ID doesn't exist"""
    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.get.return_value = None

        text = "Please check @todo:999"
        formatted = format_text_with_todo_links(text)
        assert '<span class="todo-reference-invalid' in formatted
        assert '@todo:999</span>' in formatted
