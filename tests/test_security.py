import pytest
import os
import sys
from unittest.mock import MagicMock
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Mock `url_for` function for Jinja context
def mock_url_for(endpoint, **values):
    return f"/{endpoint}"

# Mock `get_flashed_messages`
def mock_get_flashed_messages():
    return []

# Mock `csrf_token`
def mock_csrf_token():
    return "mock-csrf-token"

# Mock `dt` function (assuming it's a datetime helper)
class MockDateTime:
    def __init__(self, value):
        self.value = value
    def strftime(self, format_string):
        return "2023-01-01"

def mock_dt(timestamp):
    return MockDateTime(timestamp)

def test_project_update_detail_xss_fix():
    # Set up Jinja environment
    template_dir = os.path.abspath("superviseme/templates")
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml'])
    )

    # Add globals that might be used in templates
    env.globals['url_for'] = mock_url_for
    env.globals['get_flashed_messages'] = mock_get_flashed_messages
    env.globals['csrf_token'] = mock_csrf_token
    env.globals['current_user'] = MagicMock(id=1, name="Test User")
    env.globals['dt'] = mock_dt

    try:
        template = env.get_template('researcher/project_update_detail.html')
    except Exception as e:
        pytest.fail(f"Could not load template: {e}")

    # Create mock update with malicious content
    mock_update = MagicMock()
    mock_update.id = 123
    mock_update.update_type = "progress"
    mock_update.author.name = "Malicious"
    mock_update.author.surname = "Actor"
    mock_update.created_at = 1672531200
    mock_update.author_id = 2  # Not current user
    # The payload: <script>alert(1)</script> followed by a newline and text
    mock_update.content = "<script>alert(1)</script>\nNew Line"

    mock_project = MagicMock()
    mock_project.id = 456
    mock_project.title = "Test Project"
    mock_project.description = "Test Description"

    # Render template
    try:
        rendered = template.render(
            update=mock_update,
            project=mock_project,
            referenced_todos=[],
            todos=[],
            is_owner=False
        )
    except Exception as e:
        pytest.fail(f"Template rendering failed: {e}")

    # Assertions
    # We expect the script tag to be escaped: &lt;script&gt;
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered, "Content was not properly escaped (XSS vulnerability)"

    # We ensure the raw payload is NOT present
    # Note: simple string check is sufficient here as <script>...</script> is unique enough
    # But checking for the exact payload substring
    payload_check = "<script>alert(1)</script>"
    assert payload_check not in rendered, "XSS Vulnerability found: Raw <script> tag present in output"

    # We expect newlines to be preserved via CSS white-space: pre-wrap, so \n should be present in source
    # (Jinja renders \n as \n in HTML source, browser handles display)
    assert "\nNew Line" in rendered, "Newline was lost or modified unexpectedly"

    # Check for the style attribute usage
    assert 'style="white-space: pre-wrap;"' in rendered, "CSS style for whitespace preservation is missing"
