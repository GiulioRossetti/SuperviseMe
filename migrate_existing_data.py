#!/usr/bin/env python3
"""
SuperviseMe Data Migration Script

This script can be used to migrate existing data from a partial database
to a newly recreated complete database.

Usage:
    python migrate_existing_data.py --source backup.db --target dashboard.db
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_table_info(db_path):
    """Get information about tables and their data in a database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    table_info = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        
        table_info[table] = {
            'count': count,
            'columns': columns
        }
    
    conn.close()
    return table_info


def migrate_compatible_data(source_db, target_db, table_name):
    """Migrate data between compatible tables"""
    
    source_conn = sqlite3.connect(source_db)
    target_conn = sqlite3.connect(target_db)
    
    try:
        # Get column info for both databases
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        source_cursor.execute(f"PRAGMA table_info({table_name})")
        source_cols = {col[1]: col[2] for col in source_cursor.fetchall()}
        
        target_cursor.execute(f"PRAGMA table_info({table_name})")
        target_cols = {col[1]: col[2] for col in target_cursor.fetchall()}
        
        # Find common columns
        common_cols = set(source_cols.keys()) & set(target_cols.keys())
        
        if not common_cols:
            print(f"❌ No compatible columns found for table {table_name}")
            return False
        
        common_cols_list = list(common_cols)
        
        # Check if there's data to migrate
        source_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = source_cursor.fetchone()[0]
        
        if count == 0:
            print(f"ℹ️  No data to migrate for table {table_name}")
            return True
        
        # Prepare migration query
        cols_str = ', '.join(common_cols_list)
        placeholders = ', '.join(['?' for _ in common_cols_list])
        
        # Fetch data from source
        source_cursor.execute(f"SELECT {cols_str} FROM {table_name}")
        data = source_cursor.fetchall()
        
        # Insert into target (with conflict handling)
        insert_query = f"INSERT OR IGNORE INTO {table_name} ({cols_str}) VALUES ({placeholders})"
        
        target_cursor.executemany(insert_query, data)
        target_conn.commit()
        
        migrated_count = target_cursor.rowcount
        print(f"✓ Migrated {migrated_count} rows for table {table_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error migrating table {table_name}: {e}")
        return False
        
    finally:
        source_conn.close()
        target_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate data from old SuperviseMe database to new one")
    parser.add_argument("--source", required=True, help="Source database file path")
    parser.add_argument("--target", required=True, help="Target database file path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without actually doing it")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.source):
        print(f"❌ Source database not found: {args.source}")
        return 1
    
    if not os.path.exists(args.target):
        print(f"❌ Target database not found: {args.target}")
        print("Run recreate_database.py first to create the target database")
        return 1
    
    print("SuperviseMe Data Migration")
    print("=" * 50)
    print(f"Source: {args.source}")
    print(f"Target: {args.target}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    # Get table information from both databases
    print("Analyzing databases...")
    source_info = get_table_info(args.source)
    target_info = get_table_info(args.target)
    
    print(f"Source database tables: {len(source_info)}")
    print(f"Target database tables: {len(target_info)}")
    print()
    
    # Find tables that exist in both databases
    common_tables = set(source_info.keys()) & set(target_info.keys())
    source_only = set(source_info.keys()) - set(target_info.keys())
    target_only = set(target_info.keys()) - set(source_info.keys())
    
    print("Table Analysis:")
    print(f"  Common tables: {len(common_tables)}")
    print(f"  Source only: {len(source_only)}")
    print(f"  Target only: {len(target_only)}")
    print()
    
    if source_only:
        print("Tables only in source (will be skipped):")
        for table in sorted(source_only):
            count = source_info[table]['count']
            print(f"  - {table} ({count} rows)")
        print()
    
    if target_only:
        print("New tables in target:")
        for table in sorted(target_only):
            print(f"  - {table}")
        print()
    
    if not common_tables:
        print("No common tables found for migration.")
        return 0
    
    print("Migration Plan:")
    migration_plan = []
    for table in sorted(common_tables):
        source_count = source_info[table]['count']
        if source_count > 0:
            migration_plan.append(table)
            print(f"  ✓ {table}: {source_count} rows")
        else:
            print(f"  - {table}: No data to migrate")
    
    if not migration_plan:
        print("\nNo data to migrate.")
        return 0
    
    if args.dry_run:
        print(f"\nDry run complete. Would migrate {len(migration_plan)} tables.")
        return 0
    
    print(f"\nStarting migration of {len(migration_plan)} tables...")
    
    # Perform migration
    successful_migrations = 0
    failed_migrations = 0
    
    for table in migration_plan:
        if migrate_compatible_data(args.source, args.target, table):
            successful_migrations += 1
        else:
            failed_migrations += 1
    
    print(f"\n{'=' * 50}")
    print("Migration Results:")
    print(f"✓ Successful: {successful_migrations}")
    print(f"❌ Failed: {failed_migrations}")
    
    if failed_migrations == 0:
        print("\n🎉 Migration completed successfully!")
        return 0
    else:
        print(f"\n⚠️  Migration completed with {failed_migrations} failures.")
        return 1


if __name__ == "__main__":
    sys.exit(main())