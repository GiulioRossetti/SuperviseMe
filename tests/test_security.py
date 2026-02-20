import pytest
import os
import sys
from unittest.mock import MagicMock

# Attempt to mock DB to avoid connection issues if environment is not perfect
# But since we want to test create_app, we need to let it run.
# The Makefile says 'test' runs pytest. Let's see if existing tests use create_app.
# tests/test_app_functionality.py (which is not in tests folder but root) imports superviseme and uses it.
# But tests/test_todo_parser.py mocks everything.

# Let's try to import create_app and run it.
# We need to set FLASK_ENV to development to avoid secure cookie requirement issues if any,
# though we are testing template filter.

# We need to make sure we don't fail on DB operations.
# The create_app function copies DB file.

def test_markdown_with_todos_xss():
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from superviseme import create_app

    # Use a dummy DB path to avoid messing with real data or needing the file
    # But create_app copies from ../data_schema/database_dashboard.db
    # We can mock shutil.copyfile to do nothing

    with pytest.MonkeyPatch.context() as m:
        m.setattr("shutil.copyfile", lambda src, dst: None)
        # Mock _stamp_sqlite_db_head as well
        m.setattr("superviseme._stamp_sqlite_db_head", lambda path: None)

        # Also mock DB init stuff if needed, but sqlite usually works fine in memory or temp file
        # create_app uses config for URI.

        # We can set SQLALCHEMY_DATABASE_URI env var to sqlite:///:memory:
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["FLASK_ENV"] = "development"
        os.environ["SECRET_KEY"] = "testing-secret-key"

        app = create_app('sqlite', skip_user_init=True)

        with app.app_context():
            from superviseme import db
            db.create_all()

            # Get the filter
            markdown_filter = app.jinja_env.filters['markdown_with_todos']
            markdown_only = app.jinja_env.filters['markdown']

            # Test XSS
            malicious = "<script>alert('xss')</script><b>bold</b>"
            output = markdown_filter(malicious)

            assert "<script>" not in output
            assert "<b>bold</b>" in output

            # Test markdown filter (without todos)
            output_md = markdown_only(malicious)
            assert "<script>" not in output_md
            assert "<b>bold</b>" in output_md

            # Test that todo parsing still works (mocking Todo query inside if needed?)
            # The filter calls format_text_with_todo_links which queries DB.
            # Since we are using in-memory DB which is empty, Todo.query.get will return None.
            # That's fine, it should return invalid todo span.

            todo_text = "Check @todo:1"
            output_todo = markdown_filter(todo_text)

            # Should contain span for invalid todo (since DB is empty)
            assert "todo-reference-invalid" in output_todo
            assert "@todo:1" in output_todo
