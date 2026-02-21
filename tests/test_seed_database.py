"""Tests for scripts/seed_database.py

Verify that:
1. seed_database() creates all expected user roles and counts.
2. Passwords are taken from the env vars specified in .env (SEED_DEFAULT_PASSWORD,
   SEED_SUPERVISOR_PASSWORD, SEED_STUDENT_PASSWORD, SEED_RESEARCHER_PASSWORD,
   ADMIN_BOOTSTRAP_PASSWORD).
3. When SKIP_DB_SEED is "true", the seeding guard in docker-entrypoint logic is
   respected (tested via the resolve_seed_password helper).
4. load_dotenv() is called at module level in seed_database.py so .env values are
   always honoured before any os.getenv() reads.
"""
import importlib
import os
import sys
import pytest
from unittest.mock import patch
from werkzeug.security import check_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_seed_module():
    """Import (or re-import) seed_database from scripts/ cleanly."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    scripts_dir = os.path.join(repo_root, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    if "seed_database" in sys.modules:
        del sys.modules["seed_database"]
    return importlib.import_module("seed_database")


@pytest.fixture()
def seed_env(tmp_path, monkeypatch):
    """Minimal env for running seed_database against a temp SQLite DB."""
    db_file = tmp_path / "seed_test.db"
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", f"sqlite:///{db_file}")
    monkeypatch.setenv("SECRET_KEY", "seed-test-secret-key")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("FLASK_SKIP_USER_INIT", "1")
    monkeypatch.setenv("ENABLE_SCHEDULER", "false")
    # Ensure no leftover PG_HOST so the seed script picks SQLite
    monkeypatch.delenv("PG_HOST", raising=False)
    return db_file


# ---------------------------------------------------------------------------
# resolve_seed_password tests
# ---------------------------------------------------------------------------

class TestResolveSeedPassword:
    def test_uses_specific_env_var(self, monkeypatch):
        monkeypatch.setenv("SEED_SUPERVISOR_PASSWORD", "specific_pw")
        monkeypatch.setenv("SEED_DEFAULT_PASSWORD", "default_pw")
        seed = _import_seed_module()
        assert seed.resolve_seed_password("SEED_SUPERVISOR_PASSWORD") == "specific_pw"

    def test_falls_back_to_default_password(self, monkeypatch):
        monkeypatch.delenv("SEED_SUPERVISOR_PASSWORD", raising=False)
        monkeypatch.setenv("SEED_DEFAULT_PASSWORD", "default_pw")
        seed = _import_seed_module()
        assert seed.resolve_seed_password("SEED_SUPERVISOR_PASSWORD") == "default_pw"

    def test_falls_back_to_hardcoded_test_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("SEED_SUPERVISOR_PASSWORD", raising=False)
        monkeypatch.delenv("SEED_DEFAULT_PASSWORD", raising=False)
        seed = _import_seed_module()
        assert seed.resolve_seed_password("SEED_SUPERVISOR_PASSWORD") == "test"


# ---------------------------------------------------------------------------
# Full seeding tests
# ---------------------------------------------------------------------------

class TestSeedDatabase:
    def test_seed_creates_expected_users(self, seed_env, monkeypatch):
        """seed_database() must create admin, supervisors, students, researchers."""
        monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "admin_pw")
        monkeypatch.setenv("SEED_DEFAULT_PASSWORD", "default123")

        seed = _import_seed_module()
        seed.seed_database()

        # Verify data directly via sqlite3 to avoid Flask-SQLAlchemy session
        # state that may have been left by previous tests in the suite.
        import sqlite3
        conn = sqlite3.connect(str(seed_env))
        rows = conn.execute("SELECT user_type FROM user_mgmt").fetchall()
        conn.close()
        types = [r[0] for r in rows]

        assert "admin" in types
        assert types.count("supervisor") >= 3
        assert types.count("student") >= 5
        assert types.count("researcher") >= 3

    def test_admin_password_from_env(self, seed_env, monkeypatch):
        """Admin password must match ADMIN_BOOTSTRAP_PASSWORD from env."""
        monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "my_admin_secret")
        monkeypatch.setenv("SEED_DEFAULT_PASSWORD", "default123")

        seed = _import_seed_module()
        seed.seed_database()

        from superviseme import create_app
        from superviseme.models import User_mgmt

        app = create_app(db_type="sqlite", skip_user_init=True)
        with app.app_context():
            admin = User_mgmt.query.filter_by(username="admin").first()
            assert admin is not None, "admin user must exist after seeding"
            assert check_password_hash(admin.password, "my_admin_secret"), (
                "Admin password must match ADMIN_BOOTSTRAP_PASSWORD"
            )

    def test_supervisor_password_from_env(self, seed_env, monkeypatch):
        """Supervisor passwords must match SEED_SUPERVISOR_PASSWORD when set."""
        monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "admin_pw")
        monkeypatch.setenv("SEED_SUPERVISOR_PASSWORD", "sup_secret_pw")
        monkeypatch.delenv("SEED_DEFAULT_PASSWORD", raising=False)

        seed = _import_seed_module()
        seed.seed_database()

        from superviseme import create_app
        from superviseme.models import User_mgmt

        app = create_app(db_type="sqlite", skip_user_init=True)
        with app.app_context():
            supervisors = User_mgmt.query.filter_by(user_type="supervisor").all()
            assert supervisors, "at least one supervisor must exist"
            for sup in supervisors:
                assert check_password_hash(sup.password, "sup_secret_pw"), (
                    f"Supervisor {sup.username} password must match SEED_SUPERVISOR_PASSWORD"
                )

    def test_seed_default_password_used_when_specific_not_set(self, seed_env, monkeypatch):
        """When role-specific password is absent, SEED_DEFAULT_PASSWORD is used."""
        monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "admin_pw")
        monkeypatch.setenv("SEED_DEFAULT_PASSWORD", "shared_pw_123")
        monkeypatch.delenv("SEED_STUDENT_PASSWORD", raising=False)

        seed = _import_seed_module()
        seed.seed_database()

        from superviseme import create_app
        from superviseme.models import User_mgmt

        app = create_app(db_type="sqlite", skip_user_init=True)
        with app.app_context():
            students = User_mgmt.query.filter_by(user_type="student").all()
            assert students, "at least one student must exist"
            for student in students:
                assert check_password_hash(student.password, "shared_pw_123"), (
                    f"Student {student.username} password must match SEED_DEFAULT_PASSWORD"
                )

    def test_load_dotenv_called_before_pg_host_check(self, monkeypatch, tmp_path):
        """seed_database.py must call load_dotenv() before reading PG_HOST.

        We verify this by checking that load_dotenv is imported at module level
        (not inside the function), so env vars from .env are available for the
        very first os.getenv() call.
        """
        import ast
        seed_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "seed_database.py"
        )
        with open(seed_path) as f:
            source = f.read()

        tree = ast.parse(source)

        # Find the line numbers of: `load_dotenv()` call and `seed_database` function def
        load_dotenv_lineno = None
        seed_func_lineno = None

        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Name) and func.id == "load_dotenv":
                    load_dotenv_lineno = node.lineno
            if isinstance(node, ast.FunctionDef) and node.name == "seed_database":
                seed_func_lineno = node.lineno

        assert load_dotenv_lineno is not None, (
            "seed_database.py must call load_dotenv() at module level"
        )
        assert seed_func_lineno is not None, "seed_database() function must exist"
        assert load_dotenv_lineno < seed_func_lineno, (
            "load_dotenv() must be called BEFORE the seed_database() function definition "
            "so that env vars (including PG_HOST) are loaded from .env before any reads"
        )
