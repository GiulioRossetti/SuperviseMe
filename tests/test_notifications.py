import sys
import os
from unittest.mock import MagicMock, patch

# Mock external dependencies
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
sys.modules['werkzeug.middleware'] = MagicMock()
sys.modules['werkzeug.middleware.proxy_fix'] = MagicMock()
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['flask_migrate'] = mock_migrate
sys.modules['authlib'] = mock_authlib
sys.modules['authlib.integrations'] = MagicMock()
sys.modules['authlib.integrations.flask_client'] = MagicMock()

# Mock superviseme and its components
mock_db = MagicMock()
mock_models = MagicMock()

sys.modules['superviseme.db'] = mock_db
sys.modules['superviseme.models'] = mock_models

# Now import the functions to test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from superviseme.utils.notifications import build_role_aware_url

def test_build_role_aware_url_user_not_found():
    """Test user not found"""
    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = None
        assert build_role_aware_url(999, 'dashboard') == '#'

def test_build_role_aware_url_dashboard_student():
    """Test dashboard URL for student"""
    mock_user = MagicMock()
    mock_user.user_type = 'student'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        assert build_role_aware_url(1, 'dashboard') == '/student/dashboard'

def test_build_role_aware_url_dashboard_supervisor():
    """Test dashboard URL for supervisor"""
    mock_user = MagicMock()
    mock_user.user_type = 'supervisor'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        assert build_role_aware_url(2, 'dashboard') == '/supervisor/dashboard'

def test_build_role_aware_url_dashboard_admin():
    """Test dashboard URL for admin"""
    mock_user = MagicMock()
    mock_user.user_type = 'admin'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        assert build_role_aware_url(3, 'dashboard') == '/admin/dashboard'

def test_build_role_aware_url_thesis_student():
    """Test thesis URL for student"""
    mock_user = MagicMock()
    mock_user.user_type = 'student'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        assert build_role_aware_url(1, 'thesis') == '/student/thesis'

def test_build_role_aware_url_thesis_supervisor_with_id():
    """Test thesis URL for supervisor with thesis ID"""
    mock_user = MagicMock()
    mock_user.user_type = 'supervisor'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        assert build_role_aware_url(2, 'thesis', thesis_id=123) == '/supervisor/thesis/123'

def test_build_role_aware_url_thesis_supervisor_no_id():
    """Test thesis URL for supervisor without thesis ID"""
    mock_user = MagicMock()
    mock_user.user_type = 'supervisor'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        # Should fallback to 'theses'
        assert build_role_aware_url(2, 'thesis') == '/supervisor/theses'

def test_build_role_aware_url_thesis_admin_with_id():
    """Test thesis URL for admin with thesis ID"""
    mock_user = MagicMock()
    mock_user.user_type = 'admin'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        assert build_role_aware_url(3, 'thesis', thesis_id=456) == '/admin/thesis/456'

def test_build_role_aware_url_thesis_todos_student():
    """Test thesis todos URL for student"""
    mock_user = MagicMock()
    mock_user.user_type = 'student'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        assert build_role_aware_url(1, 'thesis_todos') == '/student/thesis#todos'

def test_build_role_aware_url_thesis_todos_supervisor_with_id():
    """Test thesis todos URL for supervisor with thesis ID"""
    mock_user = MagicMock()
    mock_user.user_type = 'supervisor'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        assert build_role_aware_url(2, 'thesis_todos', thesis_id=789) == '/supervisor/thesis/789#todos'

def test_build_role_aware_url_thesis_todos_supervisor_no_id():
    """Test thesis todos URL for supervisor without thesis ID"""
    mock_user = MagicMock()
    mock_user.user_type = 'supervisor'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        # Should fallback to generic thesis#todos
        assert build_role_aware_url(2, 'thesis_todos') == '/supervisor/thesis#todos'

def test_build_role_aware_url_thesis_todos_admin():
    """Test thesis todos URL for admin"""
    mock_user = MagicMock()
    mock_user.user_type = 'admin'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        # Current implementation falls back to else for admin
        assert build_role_aware_url(3, 'thesis_todos', thesis_id=101) == '/admin/thesis#todos'

def test_build_role_aware_url_generic_path():
    """Test generic path URL"""
    mock_user = MagicMock()
    mock_user.user_type = 'student'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        assert build_role_aware_url(1, 'profile') == '/student/profile'

def test_build_role_aware_url_unknown_role():
    """Test URL generation for unknown role"""
    mock_user = MagicMock()
    mock_user.user_type = 'guest'

    with patch('superviseme.utils.notifications.User_mgmt') as MockUser:
        MockUser.query.get.return_value = mock_user
        # Prefix should be empty
        assert build_role_aware_url(4, 'dashboard') == 'dashboard'
