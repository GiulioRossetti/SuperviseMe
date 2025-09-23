#!/usr/bin/env python3
"""
Database migration script to add Todo_Reference table
"""
from superviseme import create_app, db
from superviseme.models import Todo_Reference

app = create_app()

with app.app_context():
    print("Creating Todo_Reference table...")
    
    # Create all tables (will only create missing ones)
    db.create_all()
    
    print("Migration completed successfully!")
    print("Todo_Reference table created.")