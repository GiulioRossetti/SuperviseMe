"""
Database migration script to add Telegram notification functionality
"""
import sqlite3
import os
import time
import json

def migrate_database():
    """
    Add new columns and tables for Telegram notifications
    """
    # Get database path
    db_path = os.path.join(os.path.dirname(__file__), 'superviseme', 'db', 'dashboard.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        # Connect directly to SQLite to add columns and tables
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check existing user_mgmt table structure
        cursor.execute("PRAGMA table_info(user_mgmt)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add Telegram fields to user_mgmt table
        if 'telegram_user_id' not in columns:
            print("Adding telegram_user_id column...")
            cursor.execute("ALTER TABLE user_mgmt ADD COLUMN telegram_user_id VARCHAR(50) NULL")
            
        if 'telegram_enabled' not in columns:
            print("Adding telegram_enabled column...")
            cursor.execute("ALTER TABLE user_mgmt ADD COLUMN telegram_enabled BOOLEAN DEFAULT 0 NOT NULL")
            
        if 'telegram_notification_types' not in columns:
            print("Adding telegram_notification_types column...")
            cursor.execute("ALTER TABLE user_mgmt ADD COLUMN telegram_notification_types TEXT NULL")
        
        # Check existing notification table structure
        cursor.execute("PRAGMA table_info(notification)")
        notification_columns = [column[1] for column in cursor.fetchall()]
        
        # Add Telegram tracking fields to notification table
        if 'telegram_sent' not in notification_columns:
            print("Adding telegram_sent column to notification table...")
            cursor.execute("ALTER TABLE notification ADD COLUMN telegram_sent BOOLEAN DEFAULT 0 NOT NULL")
            
        if 'telegram_sent_at' not in notification_columns:
            print("Adding telegram_sent_at column to notification table...")
            cursor.execute("ALTER TABLE notification ADD COLUMN telegram_sent_at INTEGER NULL")
        
        # Create telegram_bot_config table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='telegram_bot_config'")
        if not cursor.fetchone():
            print("Creating telegram_bot_config table...")
            cursor.execute("""
                CREATE TABLE telegram_bot_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_token VARCHAR(200) NOT NULL,
                    bot_username VARCHAR(100) NOT NULL,
                    webhook_url VARCHAR(500) NULL,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    notification_types TEXT NOT NULL,
                    frequency_settings TEXT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
        
        # Set default notification types for existing users (supervisors and students)
        default_types = ['new_update', 'new_feedback', 'todo_assigned', 'thesis_status_change']
        default_types_json = json.dumps(default_types)
        
        cursor.execute("""
            UPDATE user_mgmt 
            SET telegram_notification_types = ?
            WHERE telegram_notification_types IS NULL 
            AND user_type IN ('student', 'supervisor')
        """, (default_types_json,))
        
        updated_users = cursor.rowcount
        if updated_users > 0:
            print(f"Set default notification types for {updated_users} users")
        
        conn.commit()
        conn.close()
        
        print("Telegram migration completed successfully!")
        print("\nNext steps:")
        print("1. Configure your Telegram bot token in the admin notification settings")
        print("2. Users can now configure their Telegram notifications in their profile")
        print("3. Install pyTelegramBotAPI: pip install pyTelegramBotAPI")
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    migrate_database()