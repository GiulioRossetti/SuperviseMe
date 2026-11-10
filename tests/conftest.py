"""
Session-level test configuration.

Several test files (test_logging_config.py, test_notifications.py) replace
sys.modules entries with MagicMock objects at *module* level (not inside
fixtures), permanently breaking tests that call create_app() and need the
real modules.

Strategy:
1. pytest_configure() snapshots ALL of sys.modules before any test file is
   collected / imported (before any module-level mocking can occur).
2. pytest_collection_finish() restores the snapshot AFTER all files are
   collected but BEFORE any test runs — this is the main defence against
   module-level mocking that runs during collection.
3. An autouse fixture (_restore_real_modules) re-applies the same restore
   before every individual test as a belt-and-suspenders measure.
4. The app() fixture explicitly depends on _restore_real_modules so pytest
   is forced to set up the restore *before* creating the Flask app.
"""

import os
import sys
import time
import tempfile
import pytest
from unittest.mock import MagicMock

# Tests never run in production mode (e.g. crypto.py refuses to start without a key there).
os.environ.setdefault("FLASK_ENV", "testing")


def _restore_snapshot(snapshot):
    """Restore sys.modules from *snapshot*, removing/replacing MagicMocks.

    Only the keys present in *snapshot* are touched (entries that were added
    after the snapshot was taken and are MagicMocks are also removed).
    """
    if not snapshot:
        return


    # Restore any snapshot entry that is currently a MagicMock.
    for key, real_module in snapshot.items():
        if isinstance(sys.modules.get(key), MagicMock):
            sys.modules[key] = real_module

    # Remove new MagicMock entries not in snapshot
    # (e.g. flask_wtf.csrf added by test_notifications.py).
    for key in list(sys.modules.keys()):
        if key not in snapshot and isinstance(sys.modules.get(key), MagicMock):
            del sys.modules[key]

    # Defensive: if flask_sqlalchemy.extension was imported while sqlalchemy
    # was mocked, its module-level bindings (sa, sa_event, sa_exc, sa_orm)
    # will be MagicMocks. Reload the module so they re-bind to the real ones.
    try:
        _real_sa = sys.modules.get("sqlalchemy")
        _fse = sys.modules.get("flask_sqlalchemy.extension")
        if (
            _fse is not None
            and _real_sa is not None
            and not isinstance(_real_sa, MagicMock)
            and any(
                isinstance(getattr(_fse, _a, None), MagicMock)
                for _a in ("sa", "sa_event", "sa_exc", "sa_orm")
            )
        ):
            import importlib as _il
            _il.reload(_fse)
    except Exception:
        pass


def pytest_configure(config):
    """Snapshot ALL of sys.modules before test files are collected."""
    # Force lazy submodules to load now so their real versions are captured.
    # Import each module individually so a single failure does not prevent the
    # rest from being snapshotted.
    for _mod in [
        "flask.globals",
        "flask_login",
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.engine.create",
        "sqlalchemy.engine.url",
        "sqlalchemy.dialects",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.base",
        "sqlalchemy.exc",
        "sqlalchemy.event",
        "sqlalchemy.orm",
        "sqlalchemy.pool",
        "sqlalchemy.util",
        "sqlalchemy.util.langhelpers",
        "werkzeug",
        "werkzeug.security",
        "flask_migrate",
        "flask_sqlalchemy",
        "flask_sqlalchemy.extension",   # ensures .sa binding is set before any mock
        "flask_sqlalchemy.cli",
        "superviseme.models",
    ]:
        try:
            __import__(_mod)
        except Exception:
            pass

    # Full snapshot after submodules are loaded.
    config._real_modules_snapshot = dict(sys.modules)


def pytest_collection_finish(session):
    """Restore sys.modules AFTER all test files are collected, BEFORE any
    test runs.

    Module-level code in test_notifications.py and test_logging_config.py
    replaces real modules with MagicMocks during collection.  This hook runs
    once after collection is complete, ensuring that every session-scoped and
    function-scoped fixture starts with a clean sys.modules regardless of
    collection order.
    """
    _restore_snapshot(getattr(session.config, "_real_modules_snapshot", {}))


@pytest.fixture(autouse=True)
def _restore_real_modules(request):
    """Restore real modules that module-level mocking may have replaced.

    test_logging_config.py and test_notifications.py replace flask, sqlalchemy,
    werkzeug, flask_migrate and others with MagicMocks at import time.
    This fixture undoes those replacements before every test so that tests
    calling create_app() always get the real modules.

    pytest_collection_finish() already performs this restore once before any
    test runs; this fixture is a belt-and-suspenders measure for cases where
    a test itself reinstates the mocks mid-session.
    """
    _restore_snapshot(getattr(request.config, "_real_modules_snapshot", {}))
    yield


# ---------------------------------------------------------------------------
# Fixtures for integration / end-to-end / authorization tests
# ---------------------------------------------------------------------------

@pytest.fixture
def app(_restore_real_modules):
    """Create an isolated Flask app backed by an in-memory SQLite database.

    The explicit _restore_real_modules dependency guarantees that sys.modules
    is restored to real modules before create_app() is called, regardless of
    the order in which pytest sets up autouse vs. explicit fixtures.
    """
    from superviseme import create_app, db as _db

    use_pg = os.environ.get("TEST_DB") == "postgresql"  # CI: run the suite on PostgreSQL (PG_* env vars)
    db_fd = db_path = None
    if use_pg:
        os.environ.pop("SQLALCHEMY_DATABASE_URI", None)
    else:
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    os.environ["WTF_CSRF_ENABLED"] = "False"
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
    os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "")
    os.environ.setdefault("ADMIN_BOOTSTRAP_PASSWORD", "")

    flask_app = create_app(db_type="postgresql" if use_pg else "sqlite", skip_user_init=True)
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False

    with flask_app.app_context():
        if use_pg:
            _db.session.remove()
            _db.drop_all()
        _db.create_all()
        yield flask_app
        _db.session.remove()
        if use_pg:
            _db.drop_all()

    if db_fd is not None:
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
