"""Tests for the automatic database schema upgrade at startup.

These tests verify that _run_db_upgrade correctly handles:
1. A fresh database (no tables) → all migrations applied.
2. An already up-to-date database → no-op (idempotent).
3. A legacy database (tables present but no alembic_version row) → stamped at
   revision 0001 then upgraded to HEAD so missing columns are added.
"""
import os
import sqlite3
import tempfile
import pytest

from superviseme import create_app


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    """Provide a minimal environment for create_app with a temp SQLite DB."""
    db_file = tmp_path / "test_dashboard.db"
    db_uri = f"sqlite:///{db_file}"

    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", db_uri)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-pytest")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("FLASK_SKIP_USER_INIT", "1")
    monkeypatch.setenv("ENABLE_SCHEDULER", "false")

    return db_file, db_uri


def _get_column_names(db_path, table):
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}
    finally:
        conn.close()


def _get_tables(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()


def test_fresh_db_gets_all_columns(app_env):
    """A brand-new empty database should have all columns after startup."""
    db_file, _ = app_env

    app = create_app(db_type="sqlite", skip_user_init=True)

    assert db_file.exists(), "Database file should be created"
    tables = _get_tables(db_file)
    assert "user_mgmt" in tables, "user_mgmt table must exist"
    columns = _get_column_names(db_file, "user_mgmt")
    assert "orcid_access_token" in columns, "orcid_access_token column must exist"
    assert "orcid_refresh_token" in columns, "orcid_refresh_token column must exist"


def test_idempotent_on_up_to_date_db(app_env):
    """Calling create_app twice on an up-to-date database should not fail."""
    create_app(db_type="sqlite", skip_user_init=True)
    # Second call should be a no-op (database already at HEAD)
    create_app(db_type="sqlite", skip_user_init=True)

    db_file, _ = app_env
    columns = _get_column_names(db_file, "user_mgmt")
    assert "orcid_access_token" in columns


def test_legacy_db_without_alembic_version_gets_orcid_columns(app_env, monkeypatch):
    """A legacy DB (tables exist but no alembic_version) should get orcid columns added."""
    db_file, _ = app_env

    # Bootstrap a "legacy" database: create the base user_mgmt table WITHOUT
    # orcid columns and WITHOUT the alembic_version table.
    conn = sqlite3.connect(str(db_file))
    conn.executescript("""
        CREATE TABLE user_mgmt (
            id INTEGER PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            name VARCHAR(15),
            surname VARCHAR(15),
            cdl VARCHAR(15),
            email VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(80) NOT NULL,
            user_type VARCHAR(10) NOT NULL DEFAULT 'student',
            joined_on INTEGER NOT NULL,
            gender VARCHAR(10),
            nationality VARCHAR(15),
            is_enabled BOOLEAN NOT NULL DEFAULT 1,
            profile_pic VARCHAR(255),
            last_activity INTEGER,
            last_activity_location VARCHAR(100),
            telegram_user_id VARCHAR(50),
            telegram_enabled BOOLEAN NOT NULL DEFAULT 0,
            telegram_notification_types TEXT
        );
    """)
    conn.commit()
    conn.close()

    # Confirm orcid columns are absent before the upgrade
    columns_before = _get_column_names(db_file, "user_mgmt")
    assert "orcid_access_token" not in columns_before

    create_app(db_type="sqlite", skip_user_init=True)

    columns_after = _get_column_names(db_file, "user_mgmt")
    assert "orcid_access_token" in columns_after, (
        "orcid_access_token must be added to a legacy DB on startup"
    )
    assert "orcid_refresh_token" in columns_after, (
        "orcid_refresh_token must be added to a legacy DB on startup"
    )

    # alembic_version table should now exist
    tables = _get_tables(db_file)
    assert "alembic_version" in tables


def test_existing_sqlite_db_is_not_replaced_on_startup(app_env):
    """
    If the DB file already exists, startup must migrate in-place and never
    replace it with a copied/seed DB.
    """
    db_file, _ = app_env

    conn = sqlite3.connect(str(db_file))
    conn.executescript("""
        CREATE TABLE keep_me (
            id INTEGER PRIMARY KEY,
            note TEXT NOT NULL
        );
        INSERT INTO keep_me (note) VALUES ('original-data');
    """)
    conn.commit()
    conn.close()

    create_app(db_type="sqlite", skip_user_init=True)

    conn = sqlite3.connect(str(db_file))
    try:
        row = conn.execute("SELECT note FROM keep_me WHERE id = 1").fetchone()
    finally:
        conn.close()

    assert row is not None, "Existing DB data must be preserved on startup"
    assert row[0] == "original-data", "Startup must not overwrite an existing DB file"
