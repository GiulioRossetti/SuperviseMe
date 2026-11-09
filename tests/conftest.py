"""
Session-level test configuration.

Several test files (test_logging_config.py, test_notifications.py) replace
sys.modules entries with MagicMock objects at *module* level (not inside
fixtures), permanently breaking tests that call create_app() and need the
real modules.

Strategy:
1. pytest_configure() snapshots ALL of sys.modules before any test file is
   collected / imported (before any module-level mocking can occur).
2. An autouse fixture restores every entry in that snapshot that has since
   been replaced with a MagicMock, and removes any new MagicMock sub-entries
   that were created while the mocks were active.
"""

import os
import sys
import time
import tempfile
import pytest
from unittest.mock import MagicMock


def pytest_configure(config):
    """Snapshot ALL of sys.modules before test files are collected."""
    # Force lazy submodules to load now so their real versions are captured.
    try:
        import flask.globals          # noqa: F401
        import flask_login            # noqa: F401
        import sqlalchemy.dialects.sqlite  # noqa: F401
        import werkzeug.security      # noqa: F401
        import flask_migrate          # noqa: F401
        import flask_sqlalchemy.cli   # noqa: F401
        import superviseme.models     # noqa: F401
    except Exception:
        pass

    # Full snapshot after submodules are loaded.
    config._real_modules_snapshot = dict(sys.modules)


@pytest.fixture(autouse=True)
def _restore_real_modules(request):
    """Restore real modules that module-level mocking may have replaced.

    test_logging_config.py and test_notifications.py replace flask, sqlalchemy,
    werkzeug, flask_migrate and others with MagicMocks at import time.
    This fixture undoes those replacements before every test so that tests
    calling create_app() always get the real modules.
    """
    snapshot = getattr(request.config, "_real_modules_snapshot", {})
    if not snapshot:
        yield
        return

    # Restore any snapshot entry that is currently a MagicMock.
    for key, real_module in snapshot.items():
        if isinstance(sys.modules.get(key), MagicMock):
            sys.modules[key] = real_module

    # Remove new MagicMock entries that were not in the snapshot at all
    # (e.g. flask_wtf.csrf added by test_notifications.py).
    for key in list(sys.modules.keys()):
        if key not in snapshot and isinstance(sys.modules.get(key), MagicMock):
            del sys.modules[key]

    yield


# ---------------------------------------------------------------------------
# Fixtures for integration / end-to-end / authorization tests
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create an isolated Flask app backed by an in-memory SQLite database."""
    from superviseme import create_app, db as _db

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    os.environ["WTF_CSRF_ENABLED"] = "False"
    os.environ.setdefault("FLASK_ENV", "testing")

    flask_app = create_app(db_type="sqlite", skip_user_init=True)
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def _make_user(user_type, username, email):
    from superviseme import db
    from superviseme.models import User_mgmt
    from werkzeug.security import generate_password_hash

    user = User_mgmt(
        username=username,
        name=username.capitalize(),
        surname="Test",
        email=email,
        password=generate_password_hash("password"),
        user_type=user_type,
        joined_on=int(time.time()),
        is_enabled=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def admin_user(app):
    return _make_user("admin", "admin_test", "admin@test.com")


@pytest.fixture
def supervisor_user(app):
    return _make_user("supervisor", "supervisor_test", "supervisor@test.com")


@pytest.fixture
def researcher_user(app):
    return _make_user("researcher", "researcher_test", "researcher@test.com")


@pytest.fixture
def student_user(app):
    return _make_user("student", "student_test", "student@test.com")
