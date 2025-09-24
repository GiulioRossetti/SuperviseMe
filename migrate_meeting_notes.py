#!/usr/bin/env python3
"""
Migration script to add meeting_note and meeting_note_reference tables
"""

from superviseme import create_app
from superviseme import db
import time

def migrate_meeting_notes():
    """Add meeting_note and meeting_note_reference tables"""
    app = create_app()
    
    with app.app_context():
        # Check if meeting_note table already exists
        try:
            db.session.execute(db.text("SELECT 1 FROM meeting_note LIMIT 1"))
            print("meeting_note table already exists, skipping migration")
            return
        except Exception:
            print("Creating meeting_note table...")

        # Create meeting_note table
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS meeting_note (
                id SERIAL PRIMARY KEY,
                thesis_id INTEGER NOT NULL REFERENCES thesis(id),
                author_id INTEGER NOT NULL REFERENCES user_mgmt(id),
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """))
        
        # Create meeting_note_reference table
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS meeting_note_reference (
                id SERIAL PRIMARY KEY,
                meeting_note_id INTEGER NOT NULL REFERENCES meeting_note(id),
                todo_id INTEGER NOT NULL REFERENCES todo(id),
                created_at INTEGER NOT NULL
            )
        """))
        
        # Create indexes for better performance
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_meeting_note_thesis_id ON meeting_note(thesis_id);
        """))
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_meeting_note_author_id ON meeting_note(author_id);
        """))
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_meeting_note_created_at ON meeting_note(created_at);
        """))
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_meeting_note_reference_note_id ON meeting_note_reference(meeting_note_id);
        """))
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_meeting_note_reference_todo_id ON meeting_note_reference(todo_id);
        """))
        
        db.session.commit()
        print("Meeting notes tables created successfully!")

if __name__ == "__main__":
    migrate_meeting_notes()