#!/usr/bin/env python3
"""
Database migration script to add notifications table
Run this script to update the database schema for the notification system
"""

import sys
import os
import sqlite3
import time

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from superviseme import create_app, db
from superviseme.models import Notification

def migrate_database():
    """Add the notifications table to the existing database"""
    
    print("Starting database migration to add notifications table...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Check if the notifications table exists
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if 'notification' not in existing_tables:
                print("Creating notifications table...")
                
                # Create the notifications table
                db.create_all()
                
                print("✅ Notifications table created successfully!")
                
                # Add some sample notifications for testing (optional)
                create_sample_notifications()
                
            else:
                print("✅ Notifications table already exists - no migration needed")
                
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            return False
    
    return True

def create_sample_notifications():
    """Create some sample notifications for testing"""
    from superviseme.models import User_mgmt, Thesis
    from superviseme.utils.notifications import create_notification, build_role_aware_url
    
    try:
        # Get some users for testing
        admin_user = User_mgmt.query.filter_by(user_type='admin').first()
        supervisor_user = User_mgmt.query.filter_by(user_type='supervisor').first()
        student_user = User_mgmt.query.filter_by(user_type='student').first()
        
        if admin_user and supervisor_user:
            # Create role-aware URL for supervisor dashboard
            action_url = build_role_aware_url(supervisor_user.id, 'dashboard')
            create_notification(
                recipient_id=supervisor_user.id,
                actor_id=admin_user.id,
                notification_type='system',
                title='Welcome to SuperviseMe Notifications!',
                message='The new notification system is now active. You will receive notifications about thesis activities.',
                action_url=action_url
            )
            print("📧 Sample notification created for supervisor")
            
        if supervisor_user and student_user:
            # Create role-aware URL for student thesis page
            action_url = build_role_aware_url(student_user.id, 'thesis')
            create_notification(
                recipient_id=student_user.id,
                actor_id=supervisor_user.id,
                notification_type='system',
                title='New Notification System',
                message='You will now receive notifications about your thesis progress and supervisor feedback.',
                action_url=action_url
            )
            print("📧 Sample notification created for student")
            
    except Exception as e:
        print(f"⚠️ Could not create sample notifications: {str(e)}")

if __name__ == "__main__":
    print("SuperviseMe Database Migration - Notifications System")
    print("=" * 50)
    
    success = migrate_database()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("The notifications system is now ready to use.")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)