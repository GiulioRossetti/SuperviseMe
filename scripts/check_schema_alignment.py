#!/usr/bin/env python3
"""
Verify that a SQLite database schema matches SQLAlchemy models.

Usage:
  python scripts/check_schema_alignment.py --db data_schema/database_dashboard.db --strict
"""

import argparse
import os
import sqlite3
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_model_schema():
    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault("SECRET_KEY", "schema-check-secret")
    os.environ.setdefault("ENABLE_SCHEDULER", "false")

    from superviseme import create_app, db

    app = create_app(db_type="sqlite", skip_user_init=True)
    with app.app_context():
        model_tables = {}
        for table_name, table in db.metadata.tables.items():
            model_tables[table_name] = {col.name for col in table.columns}
    return model_tables


def _load_sqlite_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [row[0] for row in cur.fetchall()]
        db_tables = {}
        for table in table_names:
            cur.execute(f"PRAGMA table_info('{table}')")
            db_tables[table] = {row[1] for row in cur.fetchall()}
        return db_tables
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if extra database tables/columns are present",
    )
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: database not found: {args.db}")
        return 2

    model_tables = _load_model_schema()
    db_tables = _load_sqlite_schema(args.db)

    missing_tables = sorted(set(model_tables) - set(db_tables))
    extra_tables = sorted(set(db_tables) - set(model_tables))

    # Ignore alembic_version if present
    if "alembic_version" in extra_tables:
        extra_tables.remove("alembic_version")

    missing_columns = []
    extra_columns = []
    for table, model_cols in model_tables.items():
        if table not in db_tables:
            continue
        db_cols = db_tables[table]
        for col in sorted(model_cols - db_cols):
            missing_columns.append((table, col))
        for col in sorted(db_cols - model_cols):
            extra_columns.append((table, col))

    has_error = False
    if missing_tables:
        has_error = True
        print("Missing tables:")
        for t in missing_tables:
            print(f"  - {t}")

    if missing_columns:
        has_error = True
        print("Missing columns:")
        for t, c in missing_columns:
            print(f"  - {t}.{c}")

    if args.strict and extra_tables:
        has_error = True
        print("Extra tables:")
        for t in extra_tables:
            print(f"  - {t}")
    elif extra_tables:
        print("Extra tables (ignored without --strict):")
        for t in extra_tables:
            print(f"  - {t}")

    if args.strict and extra_columns:
        has_error = True
        print("Extra columns:")
        for t, c in extra_columns:
            print(f"  - {t}.{c}")
    elif extra_columns:
        print("Extra columns (ignored without --strict):")
        for t, c in extra_columns:
            print(f"  - {t}.{c}")

    if has_error:
        print("Schema alignment check: FAILED")
        return 1

    print("Schema alignment check: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
