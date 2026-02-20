#!/usr/bin/env python3
"""
SuperviseMe Database Recreation Script

This script completely recreates the database from scratch based on the models.py definitions.
It supports both SQLite and PostgreSQL databases.

Usage:
    python recreate_database.py --db-type sqlite
    python recreate_database.py --db-type postgresql
"""

import os
import sys
import shutil
import argparse
import time
from datetime import datetime
from werkzeug.security import generate_password_hash

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from superviseme import create_app, db
from superviseme.models import *  # Import all models


def backup_existing_database(db_path):
    """Create a backup of existing database if it exists"""
    if os.path.exists(db_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{db_path}.backup_{timestamp}"
        shutil.copy2(db_path, backup_path)
        print(f"✓ Backed up existing database to: {backup_path}")
        return backup_path
    return None


def recreate_sqlite_database(app, force=False):
    """Recreate SQLite database with all tables"""
    
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    
    if not force and os.path.exists(db_path):
        response = input(f"Database {db_path} exists. Recreate? (y/N): ")
        if response.lower() != 'y':
            print("Operation cancelled.")
            return False
    
    # Backup existing database
    backup_path = backup_existing_database(db_path)
    
    # Ensure db directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Remove existing database
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✓ Removed existing database: {db_path}")
    
    # Create all tables
    with app.app_context():
        print("Creating all database tables...")
        db.create_all()
        print("✓ All tables created successfully")
        
        # Create default admin user
        create_default_admin()
        print("✓ Default admin user created")
        
        # Verify table creation
        verify_tables()
        
    return True


def recreate_postgresql_database(app, force=False):
    """Recreate PostgreSQL database with all tables"""
    
    # Extract connection details
    uri = app.config['SQLALCHEMY_DATABASE_URI']
    print(f"PostgreSQL URI: {uri}")
    
    if not force:
        response = input("Recreate PostgreSQL database? This will DROP ALL DATA! (y/N): ")
        if response.lower() != 'y':
            print("Operation cancelled.")
            return False
    
    # Import PostgreSQL modules
    from sqlalchemy import create_engine, text
    import urllib.parse
    
    # Parse the database URI
    parsed = urllib.parse.urlparse(uri)
    user = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port or 5432
    dbname = parsed.path[1:]  # Remove leading slash
    
    print(f"Connecting to PostgreSQL: {user}@{host}:{port}/{dbname}")
    
    # Connect to postgres database to manage target database
    admin_uri = f"postgresql://{user}:{password}@{host}:{port}/postgres"
    admin_engine = create_engine(admin_uri)
    
    try:
        # Drop and recreate database
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Terminate existing connections to the database
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{dbname}' AND pid != pg_backend_pid()
            """))
            
            # Drop database if exists
            conn.execute(text(f"DROP DATABASE IF EXISTS {dbname}"))
            print(f"✓ Dropped database: {dbname}")
            
            # Create database
            conn.execute(text(f"CREATE DATABASE {dbname}"))
            print(f"✓ Created database: {dbname}")
    
    except Exception as e:
        print(f"Error managing PostgreSQL database: {e}")
        return False
    finally:
        admin_engine.dispose()
    
    # Create tables in the new database
    with app.app_context():
        print("Creating all database tables...")
        db.create_all()
        print("✓ All tables created successfully")
        
        # Create default admin user
        create_default_admin()
        print("✓ Default admin user created")
        
        # Verify table creation
        verify_tables()
    
    return True


def create_default_admin():
    """Create default admin user"""
    
    # Check if admin user already exists
    existing_admin = User_mgmt.query.filter_by(username="admin").first()
    if existing_admin:
        print("Admin user already exists, skipping creation")
        return
    
    bootstrap_password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")
    if not bootstrap_password:
        raise RuntimeError(
            "ADMIN_BOOTSTRAP_PASSWORD must be set to create the bootstrap admin user."
        )

    # Create admin user
    hashed_pw = generate_password_hash(bootstrap_password, method="pbkdf2:sha256")
    admin_user = User_mgmt(
        username="admin",
        name="System",
        surname="Administrator", 
        email="admin@superviseme.local",
        password=hashed_pw,
        user_type="admin",
        joined_on=int(time.time())
    )
    
    db.session.add(admin_user)
    db.session.commit()


def verify_tables():
    """Verify that all expected tables were created"""
    
    expected_tables = [
        'user_mgmt', 'thesis', 'thesis_status', 'thesis_supervisor', 'thesis_tag',
        'update_tag', 'thesis_update', 'resource', 'thesis_objective', 'thesis_hypothesis',
        'todo', 'todo_reference', 'notification', 'meeting_note', 'meeting_note_reference',
        'telegram_bot_config', 'research_project', 'research_project_collaborator',
        'supervisor_role', 'research_project_status', 'research_project_update',
        'research_project_resource', 'research_project_objective', 'research_project_hypothesis',
        'research_project_todo', 'research_project_meeting_note', 'research_project_todo_reference',
        'research_project_meeting_note_reference'
    ]
    
    # Get actual tables from database
    inspector = db.inspect(db.engine)
    actual_tables = inspector.get_table_names()
    
    print(f"\nExpected tables: {len(expected_tables)}")
    print(f"Created tables: {len(actual_tables)}")
    
    missing_tables = set(expected_tables) - set(actual_tables)
    extra_tables = set(actual_tables) - set(expected_tables)
    
    if missing_tables:
        print(f"⚠️  Missing tables: {missing_tables}")
    
    if extra_tables:
        print(f"ℹ️  Extra tables: {extra_tables}")
    
    if not missing_tables:
        print("✓ All expected tables created successfully!")
    
    # Print summary of all tables
    print(f"\nAll tables in database:")
    for table in sorted(actual_tables):
        print(f"  - {table}")


def test_database_functionality(app):
    """Test basic database functionality"""
    
    print("\nTesting database functionality...")
    
    with app.app_context():
        # Test user creation
        test_user = User_mgmt(
            username="test_user",
            name="Test",
            surname="User",
            email="test@example.com",
            password=generate_password_hash("testpass"),
            user_type="student",
            joined_on=int(time.time())
        )
        
        db.session.add(test_user)
        db.session.commit()
        
        # Test user retrieval
        retrieved_user = User_mgmt.query.filter_by(username="test_user").first()
        assert retrieved_user is not None, "Failed to retrieve test user"
        assert retrieved_user.name == "Test", "User data incorrect"
        
        # Test thesis creation
        test_thesis = Thesis(
            title="Test Thesis",
            description="This is a test thesis",
            author_id=retrieved_user.id,
            created_at=int(time.time())
        )
        
        db.session.add(test_thesis)
        db.session.commit()
        
        # Test thesis retrieval
        retrieved_thesis = Thesis.query.filter_by(title="Test Thesis").first()
        assert retrieved_thesis is not None, "Failed to retrieve test thesis"
        assert retrieved_thesis.author_id == retrieved_user.id, "Thesis relationship incorrect"
        
        # Clean up test data
        db.session.delete(retrieved_thesis)
        db.session.delete(retrieved_user)
        db.session.commit()
        
        print("✓ Database functionality test passed!")


def main():
    parser = argparse.ArgumentParser(description="Recreate SuperviseMe database from scratch")
    parser.add_argument(
        "--db-type", 
        choices=["sqlite", "postgresql"], 
        default="sqlite",
        help="Database type to recreate"
    )
    parser.add_argument(
        "--force", 
        action="store_true",
        help="Force recreation without confirmation prompts"
    )
    parser.add_argument(
        "--test",
        action="store_true", 
        help="Run functionality tests after recreation"
    )
    
    args = parser.parse_args()
    
    print(f"SuperviseMe Database Recreation")
    print(f"Database type: {args.db_type}")
    print(f"Force mode: {args.force}")
    print("=" * 50)
    
    # Create Flask app
    try:
        app = create_app(db_type=args.db_type, skip_user_init=True)
        print(f"✓ Flask app created with {args.db_type} configuration")
    except Exception as e:
        print(f"❌ Failed to create Flask app: {e}")
        return 1
    
    # Recreate database based on type
    success = False
    try:
        if args.db_type == "sqlite":
            success = recreate_sqlite_database(app, force=args.force)
        elif args.db_type == "postgresql":
            success = recreate_postgresql_database(app, force=args.force)
        
        if success:
            print(f"\n✓ Database recreation completed successfully!")
            
            # Run tests if requested
            if args.test:
                test_database_functionality(app)
                
        else:
            print(f"\n❌ Database recreation failed or was cancelled")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error during database recreation: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print(f"\n{'='*50}")
    print(f"Database recreation complete!")
    print(f"You can now start the application with:")
    print(f"python superviseme.py --db {args.db_type}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
