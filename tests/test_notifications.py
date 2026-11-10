import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# sys.modules mocking — scoped to this test module only
# ---------------------------------------------------------------------------
# All mock objects are defined at module level (harmless: they're just objects).
# The *patching* of sys.modules is started here with patch.dict so that the
# module-level import of build_role_aware_url (below) succeeds, and is stopped
# via the autouse module-scoped fixture _cleanup_notification_mocks so that
# sys.modules is properly restored after all tests in this file complete.
# This replaces the previous pattern of bare `sys.modules[x] = MagicMock()`
# assignments which permanently corrupted sys.modules for every subsequent
# test module in the same pytest run.
# ---------------------------------------------------------------------------

mock_flask = MagicMock()
mock_sqlalchemy = MagicMock()
mock_login = MagicMock()
mock_mail = MagicMock()
mock_wtf = MagicMock()
mock_markdown = MagicMock()
mock_moment = MagicMock()
mock_werkzeug = MagicMock()
mock_migrate = MagicMock()
mock_authlib = MagicMock()
mock_db = MagicMock()
mock_models = MagicMock()

_MOCK_MODULES = {
    'flask': mock_flask,
    'flask_sqlalchemy': mock_sqlalchemy,
    'flask_login': mock_login,
    'flask_mail': mock_mail,
    'flask_wtf': mock_wtf,
    'flask_wtf.csrf': MagicMock(),
    'markdown': mock_markdown,
    'flask_moment': mock_moment,
    'werkzeug': mock_werkzeug,
    'werkzeug.security': MagicMock(),
    'werkzeug.middleware': MagicMock(),
    'werkzeug.middleware.proxy_fix': MagicMock(),
    'sqlalchemy': MagicMock(),
    'flask_migrate': mock_migrate,
    'authlib': mock_authlib,
    'authlib.integrations': MagicMock(),
    'authlib.integrations.flask_client': MagicMock(),
    'superviseme.db': mock_db,
    'superviseme.models': mock_models,
}

# Start the patcher at import/collection time so the import below works.
_patcher = patch.dict('sys.modules', _MOCK_MODULES)
_patcher.start()

# Now import the function to test (needs mocks active).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from superviseme.utils.notifications import build_role_aware_url  # noqa: E402

# The module under test was imported against mocked dependencies. Keep a handle on it and
# stop the sys.modules patch right away: if it stayed active until the module-level fixture
# teardown it would cover the *collection* of every test file sorted after this one
# (test_ui_pages.py, ...), which would then bind mocked models/db at import time.
_NOTIF_NAME = "superviseme.utils.notifications"
_notif_module = sys.modules[_NOTIF_NAME]
_patcher.stop()


@pytest.fixture(autouse=True, scope="module")
def _cleanup_notification_mocks():
    """Expose the mock-bound module to this file's tests (so patch("superviseme.utils.notifications.X")
    targets it) and put everything back afterwards."""
    import importlib
    pkg = importlib.import_module("superviseme.utils")  # the real package, as seen by patch()
    prev_attr = getattr(pkg, "notifications", None)
    saved = sys.modules.get(_NOTIF_NAME)
    sys.modules[_NOTIF_NAME] = _notif_module
    pkg.notifications = _notif_module
    yield
    if saved is None:
        sys.modules.pop(_NOTIF_NAME, None)
    else:
        sys.modules[_NOTIF_NAME] = saved
    if prev_attr is None:
        if hasattr(pkg, "notifications"):
            del pkg.notifications
    else:
        pkg.notifications = prev_attr


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_build_role_aware_url_user_not_found():
    """Test user not found"""
    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = None
        assert build_role_aware_url(999, 'dashboard') == '#'

def test_build_role_aware_url_dashboard_student():
    """Test dashboard URL for student"""
    mock_user = MagicMock()
    mock_user.user_type = 'student'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        assert build_role_aware_url(1, 'dashboard') == '/student/dashboard'

def test_build_role_aware_url_dashboard_supervisor():
    """Test dashboard URL for supervisor"""
    mock_user = MagicMock()
    mock_user.user_type = 'supervisor'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        assert build_role_aware_url(2, 'dashboard') == '/supervisor/dashboard'

def test_build_role_aware_url_dashboard_admin():
    """Test dashboard URL for admin"""
    mock_user = MagicMock()
    mock_user.user_type = 'admin'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        assert build_role_aware_url(3, 'dashboard') == '/admin/dashboard'

def test_build_role_aware_url_thesis_student():
    """Test thesis URL for student"""
    mock_user = MagicMock()
    mock_user.user_type = 'student'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        assert build_role_aware_url(1, 'thesis') == '/student/thesis'

def test_build_role_aware_url_thesis_supervisor_with_id():
    """Test thesis URL for supervisor with thesis ID"""
    mock_user = MagicMock()
    mock_user.user_type = 'supervisor'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        assert build_role_aware_url(2, 'thesis', thesis_id=123) == '/supervisor/thesis/123'

def test_build_role_aware_url_thesis_supervisor_no_id():
    """Test thesis URL for supervisor without thesis ID"""
    mock_user = MagicMock()
    mock_user.user_type = 'supervisor'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        # Should fallback to 'theses'
        assert build_role_aware_url(2, 'thesis') == '/supervisor/theses'

def test_build_role_aware_url_thesis_admin_with_id():
    """Test thesis URL for admin with thesis ID"""
    mock_user = MagicMock()
    mock_user.user_type = 'admin'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        assert build_role_aware_url(3, 'thesis', thesis_id=456) == '/admin/thesis/456'

def test_build_role_aware_url_thesis_todos_student():
    """Test thesis todos URL for student"""
    mock_user = MagicMock()
    mock_user.user_type = 'student'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        assert build_role_aware_url(1, 'thesis_todos') == '/student/thesis#todos'

def test_build_role_aware_url_thesis_todos_supervisor_with_id():
    """Test thesis todos URL for supervisor with thesis ID"""
    mock_user = MagicMock()
    mock_user.user_type = 'supervisor'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        assert build_role_aware_url(2, 'thesis_todos', thesis_id=789) == '/supervisor/thesis/789#todos'

def test_build_role_aware_url_thesis_todos_supervisor_no_id():
    """Test thesis todos URL for supervisor without thesis ID"""
    mock_user = MagicMock()
    mock_user.user_type = 'supervisor'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        # Should fallback to generic thesis#todos
        assert build_role_aware_url(2, 'thesis_todos') == '/supervisor/thesis#todos'

def test_build_role_aware_url_thesis_todos_admin():
    """Test thesis todos URL for admin"""
    mock_user = MagicMock()
    mock_user.user_type = 'admin'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        # Current implementation falls back to else for admin
        assert build_role_aware_url(3, 'thesis_todos', thesis_id=101) == '/admin/thesis#todos'

def test_build_role_aware_url_generic_path():
    """Test generic path URL"""
    mock_user = MagicMock()
    mock_user.user_type = 'student'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        assert build_role_aware_url(1, 'profile') == '/student/profile'

def test_build_role_aware_url_unknown_role():
    """Test URL generation for unknown role"""
    mock_user = MagicMock()
    mock_user.user_type = 'guest'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser, patch('superviseme.utils.notifications.db') as MockDb:
        MockDb.session.get.return_value = mock_user
        # Prefix should be empty
        assert build_role_aware_url(4, 'dashboard') == 'dashboard'
