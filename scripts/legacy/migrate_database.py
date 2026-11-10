"""
Database migration script to add activity tracking columns
"""
import sqlite3
import os
import time

def migrate_database():
    """
    Add new columns for activity tracking to existing database
    """
    # Get database path
    db_path = os.path.join(os.path.dirname(__file__), '..', 'superviseme', 'db', 'dashboard.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        # Connect directly to SQLite to add columns
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(user_mgmt)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'last_activity' not in columns:
            print("Adding last_activity column...")
            cursor.execute("ALTER TABLE user_mgmt ADD COLUMN last_activity INTEGER NULL")
            
        if 'last_activity_location' not in columns:
            print("Adding last_activity_location column...")
            cursor.execute("ALTER TABLE user_mgmt ADD COLUMN last_activity_location VARCHAR(100) NULL")
        
        # Add some sample activity data for testing
        current_time = int(time.time())
        
        # Get student IDs
        cursor.execute("SELECT id FROM user_mgmt WHERE user_type = 'student' LIMIT 3")
        students = cursor.fetchall()
        
        if len(students) >= 3:
            # Student 1: Recently active (1 day ago)
            cursor.execute(
                "UPDATE user_mgmt SET last_activity = ?, last_activity_location = ? WHERE id = ?",
                (current_time - (1 * 24 * 60 * 60), 'student_dashboard', students[0][0])
            )
            
            # Student 2: Inactive (3 weeks ago)
            cursor.execute(
                "UPDATE user_mgmt SET last_activity = ?, last_activity_location = ? WHERE id = ?",
                (current_time - (21 * 24 * 60 * 60), 'posting_thesis_update', students[1][0])
            )
            
            # Student 3: Moderately active (1 week ago)
            cursor.execute(
                "UPDATE user_mgmt SET last_activity = ?, last_activity_location = ? WHERE id = ?",
                (current_time - (7 * 24 * 60 * 60), 'thesis_detail', students[2][0])
            )
            
            print("Added sample activity data for testing")
        
        conn.commit()
        conn.close()
        
        print("Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    migrate_database()