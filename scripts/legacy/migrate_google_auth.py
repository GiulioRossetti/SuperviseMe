import sqlite3
import os

def add_column(db_path, table, col_name, col_def):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
        print(f"Added column {col_name} {col_def} to {table} in {db_path}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"Column {col_name} already exists in {table} in {db_path}")
        else:
            print(f"Error adding column {col_name} to {table} in {db_path}: {e}")
    conn.commit()
    conn.close()

def create_unique_index(db_path, table, column):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        index_name = f"idx_{table}_{column}_unique"
        cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table}({column})")
        print(f"Created unique index on {table}({column}) in {db_path}")
    except sqlite3.OperationalError as e:
        print(f"Error creating index on {table}({column}) in {db_path}: {e}")
    conn.commit()
    conn.close()

def main():
    # Adjust paths relative to repo root
    db_paths = [
        "superviseme/db/dashboard.db",
        "data_schema/database_dashboard.db"
    ]

    # (col_name, col_def)
    columns = [
        ("is_enabled", "BOOLEAN DEFAULT 1 NOT NULL"),
        ("google_id", "VARCHAR(100)"),
        ("profile_pic", "VARCHAR(255)")
    ]

    for db_path in db_paths:
        if os.path.exists(db_path):
            print(f"Updating {db_path}...")
            for col_name, col_def in columns:
                add_column(db_path, "user_mgmt", col_name, col_def)

            # Create unique index for google_id
            create_unique_index(db_path, "user_mgmt", "google_id")
        else:
            print(f"Database {db_path} not found.")

if __name__ == "__main__":
    main()
