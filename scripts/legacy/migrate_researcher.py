#!/usr/bin/env python3
"""
Migration script to add researcher role and research projects functionality.
This script adds the new tables and data for the researcher feature.
"""

import os
import sys
import time
from sqlalchemy import create_engine, text, MetaData, Table, inspect
from werkzeug.security import generate_password_hash

def get_db_engine():
    """Get database engine based on environment"""
    # Use postgresql for Docker environment, sqlite for local development
    if os.getenv("PG_HOST"):
        user = os.getenv("PG_USER", "postgres")
        password = os.getenv("PG_PASSWORD", "password")
        host = os.getenv("PG_HOST", "localhost")
        port = os.getenv("PG_PORT", "5432")
        dbname = os.getenv("PG_DBNAME", "dashboard")
        return create_engine(f"postgresql://{user}:{password}@{host}:{port}/{dbname}")
    else:
        # SQLite local development
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "..", "superviseme", "db", "dashboard.db")
        return create_engine(f"sqlite:///{db_path}")

def migrate_database():
    """Run the migration"""
    print("Starting researcher role migration...")
    
    engine = get_db_engine()
    
    with engine.connect() as connection:
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = 'sqlite' in str(engine.url)
        
        print("Checking current database schema...")
        
        # Check if the new tables already exist
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        new_tables = [
            'research_project', 'research_project_collaborator', 'supervisor_role',
            'research_project_status', 'research_project_update', 'research_project_resource',
            'research_project_objective', 'research_project_hypothesis', 'research_project_todo',
            'research_project_meeting_note', 'research_project_todo_reference', 'research_project_meeting_note_reference'
        ]
        tables_to_create = [table for table in new_tables if table not in existing_tables]
        
        if not tables_to_create:
            print("Migration already applied - all tables exist.")
            return
        
        print(f"Creating new tables: {tables_to_create}")
        
        try:
            # Create ResearchProject table
            if 'research_project' in tables_to_create:
                print("Creating research_project table...")
                if is_sqlite:
                    create_research_project_sql = """
                    CREATE TABLE research_project (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title VARCHAR(100) NOT NULL,
                        description TEXT NOT NULL,
                        researcher_id INTEGER NOT NULL,
                        frozen BOOLEAN DEFAULT 0,
                        level TEXT,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (researcher_id) REFERENCES user_mgmt(id)
                    );
                    """
                else:
                    create_research_project_sql = """
                    CREATE TABLE research_project (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(100) NOT NULL,
                        description TEXT NOT NULL,
                        researcher_id INTEGER NOT NULL,
                        frozen BOOLEAN DEFAULT FALSE,
                        level TEXT,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (researcher_id) REFERENCES user_mgmt(id)
                    );
                    """
                connection.execute(text(create_research_project_sql))
            
            # Create ResearchProject_Collaborator table
            if 'research_project_collaborator' in tables_to_create:
                print("Creating research_project_collaborator table...")
                if is_sqlite:
                    create_collaborator_sql = """
                    CREATE TABLE research_project_collaborator (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        collaborator_id INTEGER NOT NULL,
                        role VARCHAR(50) NOT NULL DEFAULT 'collaborator',
                        added_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (collaborator_id) REFERENCES user_mgmt(id)
                    );
                    """
                else:
                    create_collaborator_sql = """
                    CREATE TABLE research_project_collaborator (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        collaborator_id INTEGER NOT NULL,
                        role VARCHAR(50) NOT NULL DEFAULT 'collaborator',
                        added_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (collaborator_id) REFERENCES user_mgmt(id)
                    );
                    """
                connection.execute(text(create_collaborator_sql))
            
            # Create Supervisor_Role table
            if 'supervisor_role' in tables_to_create:
                print("Creating supervisor_role table...")
                if is_sqlite:
                    create_supervisor_role_sql = """
                    CREATE TABLE supervisor_role (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        researcher_id INTEGER NOT NULL,
                        granted_by INTEGER NOT NULL,
                        granted_at INTEGER NOT NULL,
                        active BOOLEAN NOT NULL DEFAULT 1,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (researcher_id) REFERENCES user_mgmt(id),
                        FOREIGN KEY (granted_by) REFERENCES user_mgmt(id)
                    );
                    """
                else:
                    create_supervisor_role_sql = """
                    CREATE TABLE supervisor_role (
                        id SERIAL PRIMARY KEY,
                        researcher_id INTEGER NOT NULL,
                        granted_by INTEGER NOT NULL,
                        granted_at INTEGER NOT NULL,
                        active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (researcher_id) REFERENCES user_mgmt(id),
                        FOREIGN KEY (granted_by) REFERENCES user_mgmt(id)
                    );
                    """
                connection.execute(text(create_supervisor_role_sql))
            
            # Create ResearchProject_Status table
            if 'research_project_status' in tables_to_create:
                print("Creating research_project_status table...")
                if is_sqlite:
                    create_status_sql = """
                    CREATE TABLE research_project_status (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id)
                    );
                    """
                else:
                    create_status_sql = """
                    CREATE TABLE research_project_status (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id)
                    );
                    """
                connection.execute(text(create_status_sql))
            
            # Create ResearchProject_Update table
            if 'research_project_update' in tables_to_create:
                print("Creating research_project_update table...")
                if is_sqlite:
                    create_update_sql = """
                    CREATE TABLE research_project_update (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        update_type VARCHAR(20) NOT NULL DEFAULT 'update',
                        parent_id INTEGER,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        content TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (author_id) REFERENCES user_mgmt(id),
                        FOREIGN KEY (parent_id) REFERENCES research_project_update(id)
                    );
                    """
                else:
                    create_update_sql = """
                    CREATE TABLE research_project_update (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        update_type VARCHAR(20) NOT NULL DEFAULT 'update',
                        parent_id INTEGER,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        content TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (author_id) REFERENCES user_mgmt(id),
                        FOREIGN KEY (parent_id) REFERENCES research_project_update(id)
                    );
                    """
                connection.execute(text(create_update_sql))
            
            # Create ResearchProject_Resource table
            if 'research_project_resource' in tables_to_create:
                print("Creating research_project_resource table...")
                if is_sqlite:
                    create_resource_sql = """
                    CREATE TABLE research_project_resource (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        resource_type VARCHAR(50) NOT NULL,
                        resource_url VARCHAR(255) NOT NULL,
                        description TEXT,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id)
                    );
                    """
                else:
                    create_resource_sql = """
                    CREATE TABLE research_project_resource (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        resource_type VARCHAR(50) NOT NULL,
                        resource_url VARCHAR(255) NOT NULL,
                        description TEXT,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id)
                    );
                    """
                connection.execute(text(create_resource_sql))
            
            # Create ResearchProject_Objective table
            if 'research_project_objective' in tables_to_create:
                print("Creating research_project_objective table...")
                if is_sqlite:
                    create_objective_sql = """
                    CREATE TABLE research_project_objective (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        description TEXT NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'active',
                        frozen BOOLEAN DEFAULT 0,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (author_id) REFERENCES user_mgmt(id)
                    );
                    """
                else:
                    create_objective_sql = """
                    CREATE TABLE research_project_objective (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        description TEXT NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'active',
                        frozen BOOLEAN DEFAULT FALSE,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (author_id) REFERENCES user_mgmt(id)
                    );
                    """
                connection.execute(text(create_objective_sql))
            
            # Create ResearchProject_Hypothesis table
            if 'research_project_hypothesis' in tables_to_create:
                print("Creating research_project_hypothesis table...")
                if is_sqlite:
                    create_hypothesis_sql = """
                    CREATE TABLE research_project_hypothesis (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        description TEXT NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'active',
                        frozen BOOLEAN DEFAULT 0,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (author_id) REFERENCES user_mgmt(id)
                    );
                    """
                else:
                    create_hypothesis_sql = """
                    CREATE TABLE research_project_hypothesis (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        description TEXT NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'active',
                        frozen BOOLEAN DEFAULT FALSE,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (author_id) REFERENCES user_mgmt(id)
                    );
                    """
                connection.execute(text(create_hypothesis_sql))
            
            # Create ResearchProject_Todo table
            if 'research_project_todo' in tables_to_create:
                print("Creating research_project_todo table...")
                if is_sqlite:
                    create_todo_sql = """
                    CREATE TABLE research_project_todo (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        assigned_to_id INTEGER,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        priority VARCHAR(10) NOT NULL DEFAULT 'medium',
                        due_date INTEGER,
                        completed_at INTEGER,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (author_id) REFERENCES user_mgmt(id),
                        FOREIGN KEY (assigned_to_id) REFERENCES user_mgmt(id)
                    );
                    """
                else:
                    create_todo_sql = """
                    CREATE TABLE research_project_todo (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        assigned_to_id INTEGER,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        priority VARCHAR(10) NOT NULL DEFAULT 'medium',
                        due_date INTEGER,
                        completed_at INTEGER,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (author_id) REFERENCES user_mgmt(id),
                        FOREIGN KEY (assigned_to_id) REFERENCES user_mgmt(id)
                    );
                    """
                connection.execute(text(create_todo_sql))
            
            # Create ResearchProject_MeetingNote table
            if 'research_project_meeting_note' in tables_to_create:
                print("Creating research_project_meeting_note table...")
                if is_sqlite:
                    create_meeting_note_sql = """
                    CREATE TABLE research_project_meeting_note (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        content TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (author_id) REFERENCES user_mgmt(id)
                    );
                    """
                else:
                    create_meeting_note_sql = """
                    CREATE TABLE research_project_meeting_note (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        content TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES research_project(id),
                        FOREIGN KEY (author_id) REFERENCES user_mgmt(id)
                    );
                    """
                connection.execute(text(create_meeting_note_sql))
            
            # Create ResearchProject_TodoReference table
            if 'research_project_todo_reference' in tables_to_create:
                print("Creating research_project_todo_reference table...")
                if is_sqlite:
                    create_todo_reference_sql = """
                    CREATE TABLE research_project_todo_reference (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        update_id INTEGER NOT NULL,
                        todo_id INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (update_id) REFERENCES research_project_update(id),
                        FOREIGN KEY (todo_id) REFERENCES research_project_todo(id)
                    );
                    """
                else:
                    create_todo_reference_sql = """
                    CREATE TABLE research_project_todo_reference (
                        id SERIAL PRIMARY KEY,
                        update_id INTEGER NOT NULL,
                        todo_id INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (update_id) REFERENCES research_project_update(id),
                        FOREIGN KEY (todo_id) REFERENCES research_project_todo(id)
                    );
                    """
                connection.execute(text(create_todo_reference_sql))
            
            # Create ResearchProject_MeetingNoteReference table
            if 'research_project_meeting_note_reference' in tables_to_create:
                print("Creating research_project_meeting_note_reference table...")
                if is_sqlite:
                    create_meeting_note_reference_sql = """
                    CREATE TABLE research_project_meeting_note_reference (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        meeting_note_id INTEGER NOT NULL,
                        todo_id INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (meeting_note_id) REFERENCES research_project_meeting_note(id),
                        FOREIGN KEY (todo_id) REFERENCES research_project_todo(id)
                    );
                    """
                else:
                    create_meeting_note_reference_sql = """
                    CREATE TABLE research_project_meeting_note_reference (
                        id SERIAL PRIMARY KEY,
                        meeting_note_id INTEGER NOT NULL,
                        todo_id INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        FOREIGN KEY (meeting_note_id) REFERENCES research_project_meeting_note(id),
                        FOREIGN KEY (todo_id) REFERENCES research_project_todo(id)
                    );
                    """
                connection.execute(text(create_meeting_note_reference_sql))
            
            # Commit the changes
            connection.commit()
            print("Migration completed successfully!")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            connection.rollback()
            raise

def add_sample_data():
    """Add sample researcher data"""
    print("Adding sample researcher data...")
    
    engine = get_db_engine()
    
    with engine.connect() as connection:
        try:
            # Check if we already have researchers
            result = connection.execute(text("SELECT COUNT(*) FROM user_mgmt WHERE user_type = 'researcher'"))
            researcher_count = result.scalar()
            
            if researcher_count > 0:
                print(f"Sample data already exists - found {researcher_count} researchers.")
                return
            
            # Create sample researchers
            current_time = int(time.time())
            hashed_pw = generate_password_hash('researcher123', method='pbkdf2:sha256')
            
            researchers_data = [
                {
                    'username': 'dr_alice',
                    'name': 'Alice',
                    'surname': 'Johnson',
                    'email': 'alice.johnson@university.edu',
                    'cdl': 'Computer Science',
                    'gender': 'Female',
                    'nationality': 'Canadian'
                },
                {
                    'username': 'dr_bob',
                    'name': 'Bob',
                    'surname': 'Williams', 
                    'email': 'bob.williams@university.edu',
                    'cdl': 'Data Science',
                    'gender': 'Male',
                    'nationality': 'American'
                }
            ]
            
            researcher_ids = []
            for researcher_data in researchers_data:
                result = connection.execute(text("""
                    INSERT INTO user_mgmt (username, name, surname, email, password, user_type, cdl, gender, nationality, joined_on)
                    VALUES (:username, :name, :surname, :email, :password, 'researcher', :cdl, :gender, :nationality, :joined_on)
                """), {
                    **researcher_data,
                    'password': hashed_pw,
                    'joined_on': current_time
                })
                
                # Get the inserted ID
                if 'sqlite' in str(engine.url):
                    researcher_id = result.lastrowid
                else:
                    # For PostgreSQL, we need to get the ID differently
                    id_result = connection.execute(text("SELECT id FROM user_mgmt WHERE username = :username"), 
                                                 {'username': researcher_data['username']})
                    researcher_id = id_result.scalar()
                
                researcher_ids.append(researcher_id)
                print(f"Created researcher: {researcher_data['name']} {researcher_data['surname']} (ID: {researcher_id})")
            
            # Create sample research projects
            projects_data = [
                {
                    'title': 'Machine Learning for Climate Prediction',
                    'description': 'A comprehensive study on using advanced ML algorithms to improve climate change prediction models.',
                    'researcher_id': researcher_ids[0],
                    'level': 'research'
                },
                {
                    'title': 'Social Network Analysis in Online Communities',
                    'description': 'Investigating patterns of interaction and influence in online social networks.',
                    'researcher_id': researcher_ids[1], 
                    'level': 'full-scale'
                }
            ]
            
            project_ids = []
            for project_data in projects_data:
                result = connection.execute(text("""
                    INSERT INTO research_project (title, description, researcher_id, level, frozen, created_at)
                    VALUES (:title, :description, :researcher_id, :level, 0, :created_at)
                """), {
                    **project_data,
                    'created_at': current_time
                })
                
                # Get the inserted project ID
                if 'sqlite' in str(engine.url):
                    project_id = result.lastrowid
                else:
                    id_result = connection.execute(text("SELECT id FROM research_project WHERE title = :title"), 
                                                 {'title': project_data['title']})
                    project_id = id_result.scalar()
                
                project_ids.append(project_id)
                print(f"Created research project: {project_data['title']} (ID: {project_id})")
            
            # Make one researcher also a supervisor (grant supervisor role to Alice)
            connection.execute(text("""
                INSERT INTO supervisor_role (researcher_id, granted_by, granted_at, active, created_at, updated_at)
                VALUES (:researcher_id, 1, :granted_at, 1, :created_at, :updated_at)
            """), {
                'researcher_id': researcher_ids[0],  # Alice
                'granted_at': current_time,
                'created_at': current_time,
                'updated_at': current_time
            })
            print(f"Granted supervisor role to {researchers_data[0]['name']} {researchers_data[0]['surname']}")
            
            # Add a collaboration (Bob collaborates on Alice's project)
            connection.execute(text("""
                INSERT INTO research_project_collaborator (project_id, collaborator_id, role, added_at)
                VALUES (:project_id, :collaborator_id, 'collaborator', :added_at)
            """), {
                'project_id': project_ids[0],  # Alice's ML project
                'collaborator_id': researcher_ids[1],  # Bob
                'added_at': current_time
            })
            print("Added collaboration between researchers")
            
            # Add sample extended project features
            print("Adding sample project features...")
            
            # Add project status for both projects
            for project_id in project_ids:
                connection.execute(text("""
                    INSERT INTO research_project_status (project_id, status, updated_at)
                    VALUES (:project_id, 'active', :updated_at)
                """), {
                    'project_id': project_id,
                    'updated_at': current_time
                })
            
            # Add sample update for first project
            connection.execute(text("""
                INSERT INTO research_project_update (project_id, author_id, update_type, content, created_at)
                VALUES (:project_id, :author_id, 'update', :content, :created_at)
            """), {
                'project_id': project_ids[0],
                'author_id': researcher_ids[0],
                'content': 'Initial project setup complete. Beginning data collection phase.',
                'created_at': current_time
            })
            
            # Add sample objective for first project
            connection.execute(text("""
                INSERT INTO research_project_objective (project_id, author_id, title, description, created_at)
                VALUES (:project_id, :author_id, :title, :description, :created_at)
            """), {
                'project_id': project_ids[0],
                'author_id': researcher_ids[0],
                'title': 'Develop Advanced ML Models',
                'description': 'Create and train machine learning models for climate prediction with improved accuracy.',
                'created_at': current_time
            })
            
            # Add sample hypothesis for first project
            connection.execute(text("""
                INSERT INTO research_project_hypothesis (project_id, author_id, title, description, created_at)
                VALUES (:project_id, :author_id, :title, :description, :created_at)
            """), {
                'project_id': project_ids[0],
                'author_id': researcher_ids[0],
                'title': 'Deep Learning Improves Climate Prediction',
                'description': 'We hypothesize that deep neural networks will outperform traditional models in climate prediction accuracy.',
                'created_at': current_time
            })
            
            # Add sample todo for first project
            connection.execute(text("""
                INSERT INTO research_project_todo (project_id, author_id, assigned_to_id, title, description, priority, created_at, updated_at)
                VALUES (:project_id, :author_id, :assigned_to_id, :title, :description, 'high', :created_at, :updated_at)
            """), {
                'project_id': project_ids[0],
                'author_id': researcher_ids[0],
                'assigned_to_id': researcher_ids[1],  # Assign to Bob
                'title': 'Literature Review',
                'description': 'Complete comprehensive literature review on ML climate models.',
                'created_at': current_time,
                'updated_at': current_time
            })
            
            # Add sample resource for first project
            connection.execute(text("""
                INSERT INTO research_project_resource (project_id, resource_type, resource_url, description, created_at)
                VALUES (:project_id, 'link', :resource_url, :description, :created_at)
            """), {
                'project_id': project_ids[0],
                'resource_url': 'https://example.com/climate-data',
                'description': 'Climate dataset repository',
                'created_at': current_time
            })
            
            print("Sample project features added successfully!")
            
            connection.commit()
            print("Sample data added successfully!")
            
        except Exception as e:
            print(f"Failed to add sample data: {e}")
            connection.rollback()
            raise

if __name__ == "__main__":
    try:
        migrate_database()
        add_sample_data()
        print("\n✅ Migration and sample data setup completed successfully!")
        print("\nSample accounts created:")
        print("- dr_alice / researcher123 (Researcher with supervisor role)")
        print("- dr_bob / researcher123 (Researcher)")
        print("\nYou can now test the researcher functionality.")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)