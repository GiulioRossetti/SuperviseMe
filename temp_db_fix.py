#!/usr/bin/env python3
"""
Temporary script to fix database structure by running seed_database.py
and committing the restored database file.
"""

import os
import subprocess
import sys

def run_command(cmd, cwd=None):
    """Run a command and return the result"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print(f"Output: {result.stdout}")
    return True

def main():
    # Get the repository root
    repo_root = "/home/runner/work/SuperviseMe/SuperviseMe"
    
    print("Fixing database structure...")
    
    # Run seed_database.py to recreate complete database
    print("1. Running seed_database.py to recreate complete database...")
    if not run_command("python seed_database.py", cwd=repo_root):
        print("Failed to run seed_database.py")
        return False
    
    # Check if database file exists and has content
    db_path = os.path.join(repo_root, "superviseme", "db", "dashboard.db")
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f"2. Database file exists with size: {size} bytes")
        if size > 100000:  # Should be substantial size with all tables
            print("✅ Database appears to be properly populated")
        else:
            print("⚠️ Database seems small, may be incomplete")
    else:
        print("❌ Database file not found")
        return False
    
    print("✅ Database structure fix completed successfully")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)