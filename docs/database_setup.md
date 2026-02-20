# SuperviseMe Database Setup

This document describes how to set up and recreate the SuperviseMe database from scratch.

## Overview

The SuperviseMe application uses a comprehensive database schema with 28 tables to manage users, theses, research projects, tasks, notifications, and more. The database supports both SQLite (for development) and PostgreSQL (for production).

## Database Tables

The complete database schema includes:

### Core Tables
- `user_mgmt` - User management and authentication
- `thesis` - Thesis projects
- `thesis_status` - Thesis status tracking
- `thesis_supervisor` - Thesis-supervisor relationships
- `thesis_tag` - Thesis tagging system
- `thesis_update` - Thesis progress updates
- `thesis_objective` - Thesis objectives
- `thesis_hypothesis` - Thesis hypotheses

### Task Management
- `todo` - Task management
- `todo_reference` - Links between tasks and updates
- `update_tag` - Tags for updates

### Communication & Resources
- `notification` - User notifications
- `meeting_note` - Meeting notes
- `meeting_note_reference` - Links between meeting notes and tasks
- `resource` - File and link resources
- `telegram_bot_config` - Telegram integration settings

### Research Projects
- `research_project` - Research project management
- `research_project_collaborator` - Project collaborators
- `research_project_status` - Project status tracking
- `research_project_update` - Project updates
- `research_project_resource` - Project resources
- `research_project_objective` - Project objectives
- `research_project_hypothesis` - Project hypotheses
- `research_project_todo` - Project tasks
- `research_project_meeting_note` - Project meeting notes
- `research_project_todo_reference` - Project task references
- `research_project_meeting_note_reference` - Project meeting note references

### Administration
- `supervisor_role` - Supervisor role management

## Database Recreation

### Automatic Recreation (Recommended)

Use the provided database recreation script to completely rebuild the database:

```bash
# Recreate SQLite database (development)
python recreate_database.py --db-type sqlite --force --test

# Recreate PostgreSQL database (production) - requires PostgreSQL service
python recreate_database.py --db-type postgresql --force --test
```

### Script Options

- `--db-type`: Choose between `sqlite` or `postgresql`
- `--force`: Skip confirmation prompts
- `--test`: Run functionality tests after recreation

### What the Script Does

1. **Backup**: Creates a timestamped backup of existing database
2. **Drop/Create**: Removes old database and creates new one
3. **Schema**: Creates all 28 tables according to models.py
4. **Admin User**: Creates default admin user (username: `admin`, password: `test`)
5. **Verification**: Confirms all expected tables were created
6. **Testing**: Optional functionality tests

### Manual Database Management

If you need to manually manage the database:

```python
from superviseme import create_app, db

# Create app with database initialization disabled
app = create_app(db_type="sqlite", skip_user_init=True)

with app.app_context():
    # Create all tables
    db.create_all()
    
    # Create admin user
    from superviseme.models import User_mgmt
    from werkzeug.security import generate_password_hash
    import time
    
    admin_user = User_mgmt(
        username="admin",
        name="System",
        surname="Administrator",
        email="admin@superviseme.local",
        password=generate_password_hash("test"),
        user_type="admin",
        joined_on=int(time.time())
    )
    db.session.add(admin_user)
    db.session.commit()
```

## Starting the Application

After database recreation, start the application:

```bash
# SQLite (development)
python superviseme.py --db sqlite --port 8080

# PostgreSQL (production)
python superviseme.py --db postgresql --port 8080
```

## Testing

Test the application functionality:

```bash
python test_app_functionality.py
```

This will verify:
- Database connectivity and queries
- Basic web endpoints
- Admin user creation
- Application startup

## Troubleshooting

### Common Issues

1. **"no such table: user_mgmt"** - Run the database recreation script
2. **Port already in use** - Use a different port with `--port` option
3. **PostgreSQL connection errors** - Ensure PostgreSQL service is running
4. **Permission errors** - Check file permissions in `superviseme/db/` directory

### Database Location

- SQLite database: `superviseme/db/dashboard.db`
- Backups: `superviseme/db/dashboard.db.backup_YYYYMMDD_HHMMSS`

### Environment Variables

For PostgreSQL, set these environment variables:

```bash
export PG_USER="postgres"
export PG_PASSWORD="your_password"
export PG_HOST="localhost"
export PG_PORT="5432"
export PG_DBNAME="superviseme"
```

## Default Credentials

After database recreation, you can log in with:
- **Username**: admin
- **Email**: admin@superviseme.local
- **Password**: test

⚠️ **Important**: Change the default admin password after first login in production!

## Migration from Old Database

If you have an existing database with partial tables, the recreation script will:
1. Create a backup of your existing database
2. Create a completely new database with all required tables
3. You can manually migrate important data from the backup if needed

The script does not attempt to migrate existing data - it creates a fresh database. If you need to preserve existing data, consider creating a custom migration script based on your specific needs.