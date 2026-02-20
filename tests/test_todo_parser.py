import sys
import os
from unittest.mock import MagicMock, patch
import pytest

# Define mocks that are needed for todo_parser to work in isolation
def get_mocks():
    return {
        'flask': MagicMock(),
        'flask_sqlalchemy': MagicMock(),
        'flask_login': MagicMock(),
        'flask_mail': MagicMock(),
        'flask_wtf': MagicMock(),
        'flask_wtf.csrf': MagicMock(),
        'flask_migrate': MagicMock(),
        'authlib': MagicMock(),
        'authlib.integrations': MagicMock(),
        'authlib.integrations.flask_client': MagicMock(),
        'markdown': MagicMock(),
        'flask_moment': MagicMock(),
        'werkzeug': MagicMock(),
        'werkzeug.security': MagicMock(),
        'sqlalchemy': MagicMock(),
        'superviseme.db': MagicMock(),
        'superviseme.models': MagicMock(),
    }

@pytest.fixture(scope="function")
def parser_module():
    """
    Fixture that patches sys.modules with mocks and imports todo_parser.
    Using function scope ensures we get a fresh import or at least clean mocks.
    """
    mocks = get_mocks()
    with patch.dict(sys.modules, mocks):
        # Ensure we can import the module even if it was imported before
        if 'superviseme.utils.todo_parser' in sys.modules:
            del sys.modules['superviseme.utils.todo_parser']

        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

        import superviseme.utils.todo_parser
        yield superviseme.utils.todo_parser

        # Cleanup is handled by patch.dict context manager restoring sys.modules

def test_parse_todo_ids(parser_module):
    """Test extraction of numeric IDs"""
    # Test @todo:ID format
    assert parser_module.parse_todo_references("Check @todo:1") == [1]
    # Test #todo-ID format
    assert parser_module.parse_todo_references("Check #todo-2") == [2]
    # Test multiple IDs
    result = parser_module.parse_todo_references("@todo:1 and #todo-2")
    assert sorted(result) == [1, 2]
    # Test case insensitivity
    assert parser_module.parse_todo_references("@TODO:3") == [3]
    assert parser_module.parse_todo_references("#TODO-4") == [4]

def test_parse_todo_titles(parser_module):
    """Test extraction of todo references by title"""
    mock_todo1 = MagicMock()
    mock_todo1.id = 10
    mock_todo1.title = "Literature Review"

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.filter.return_value.all.return_value = [mock_todo1]

        assert parser_module.parse_todo_references('@todo:"Literature Review"') == [10]
        MockTodo.title.ilike.assert_called_with('%Literature Review%')

def test_parse_todo_slugs(parser_module):
    """Test extraction of todo references by slug"""
    mock_todo = MagicMock()
    mock_todo.id = 30

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.filter.return_value.all.return_value = [mock_todo]
        assert parser_module.parse_todo_references("@todo:my-task") == [30]
        MockTodo.title.ilike.assert_called_with('%my task%')

def test_parse_mixed_references(parser_module):
    """Test mixed ID and title references"""
    mock_todo = MagicMock()
    mock_todo.id = 100

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.filter.return_value.all.return_value = [mock_todo]
        result = parser_module.parse_todo_references("Finish @todo:1 and start @todo:project-plan")
        assert sorted(result) == [1, 100]

def test_parse_duplicates(parser_module):
    """Test that duplicate references are removed"""
    assert parser_module.parse_todo_references("@todo:1 and @todo:1") == [1]

    mock_todo = MagicMock()
    mock_todo.id = 1
    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.filter.return_value.all.return_value = [mock_todo]
        result = parser_module.parse_todo_references("@todo:1 and @todo:\"Title of 1\"")
        assert result == [1]

def test_parse_no_matches(parser_module):
    """Test when no references are present"""
    assert parser_module.parse_todo_references("Just some regular text") == []
    assert parser_module.parse_todo_references("") == []

def test_parse_multiple_title_matches(parser_module):
    """Test when one title search returns multiple todos"""
    mock_todo1 = MagicMock()
    mock_todo1.id = 40
    mock_todo2 = MagicMock()
    mock_todo2.id = 41

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.filter.return_value.all.return_value = [mock_todo1, mock_todo2]

        result = parser_module.parse_todo_references("@todo:search-term")
        assert sorted(result) == [40, 41]

def test_format_text_with_todo_links(parser_module):
    """Test formatting text with todo links"""
    mock_todo = MagicMock()
    mock_todo.id = 1
    mock_todo.title = "Test Todo"

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.get.return_value = mock_todo

        text = "Please check @todo:1"
        formatted = parser_module.format_text_with_todo_links(text)
        assert '<a href="/supervisor/todo/1"' in formatted
        assert 'title="Test Todo"' in formatted
        assert '@todo:1</a>' in formatted

def test_format_text_with_hash_todo_links(parser_module):
    """Test formatting text with #todo-ID links"""
    mock_todo = MagicMock()
    mock_todo.id = 2
    mock_todo.title = "Hash Todo"

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.get.return_value = mock_todo

        text = "Please check #todo-2"
        formatted = parser_module.format_text_with_todo_links(text)
        assert '<a href="/supervisor/todo/2"' in formatted
        assert '#todo-2</a>' in formatted

def test_format_text_invalid_todo(parser_module):
    """Test formatting text when todo ID doesn't exist"""
    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.get.return_value = None

        text = "Please check @todo:999"
        formatted = parser_module.format_text_with_todo_links(text)
        assert '<span class="todo-reference-invalid' in formatted
        assert '@todo:999</span>' in formatted

def test_format_text_empty():
    """Test empty text handling"""
    assert format_text_with_todo_links(None) is None
    assert format_text_with_todo_links("") == ""

def test_format_text_custom_base_url():
    """Test custom base URL"""
    mock_todo = MagicMock()
    mock_todo.id = 1
    mock_todo.title = "Test Todo"

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.get.return_value = mock_todo

        text = "Check @todo:1"
        formatted = format_text_with_todo_links(text, base_url="/student/")
        assert '<a href="/student/todo/1"' in formatted

def test_format_text_exception_handling():
    """Test exception handling during replacement"""
    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        # Mock get to raise exception
        MockTodo.query.get.side_effect = Exception("Database error")

        text = "Check @todo:1 and #todo-2"
        # Should return original text despite exception
        assert format_text_with_todo_links(text) == text

def test_format_text_invalid_hash_todo():
    """Test invalid #todo-ID format"""
    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        MockTodo.query.get.return_value = None

        text = "Check #todo-999"
        formatted = format_text_with_todo_links(text)
        assert '<span class="todo-reference-invalid' in formatted
        assert '#todo-999</span>' in formatted

def test_format_text_mixed_content():
    """Test mixed valid and invalid todos"""
    mock_todo = MagicMock()
    mock_todo.id = 1
    mock_todo.title = "Valid Todo"

    with patch('superviseme.utils.todo_parser.Todo') as MockTodo:
        def side_effect(todo_id):
            if todo_id == 1:
                return mock_todo
            return None

        MockTodo.query.get.side_effect = side_effect

        text = "Review @todo:1 and @todo:999"
        formatted = format_text_with_todo_links(text)

        # Valid one should be a link
        assert '<a href="/supervisor/todo/1"' in formatted
        # Invalid one should be a span
        assert '<span class="todo-reference-invalid' in formatted
        assert '@todo:999</span>' in formatted
