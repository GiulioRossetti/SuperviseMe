# SuperviseMe

A comprehensive web application for thesis supervision and research project management in academic environments. SuperviseMe streamlines the process of thesis supervision by providing dedicated dashboards for administrators, supervisors, researchers, and students, along with robust user management and project tracking capabilities.

📘 **[Read the Full Documentation](https://giuliorossetti.github.io/SuperviseMe/)**

## 🎯 Project Overview

SuperviseMe is a Flask-based web application designed to facilitate thesis supervision and research collaboration in universities and academic institutions. The platform provides role-based access control with distinct interfaces for administrators, supervisors, researchers, and students, each tailored to their specific needs and responsibilities.

## ✨ Key Features

### 🔐 Authentication & Authorization
- **Secure Login System**: Email-based authentication with password hashing using PBKDF2-SHA256
- **Role-Based Access Control**: Separate dashboards and permissions for admins, supervisors, researchers, and students
- **Session Management**: Secure session handling with remember-me functionality
- **Logout Protection**: Proper session cleanup and redirect handling

### 👨‍💼 Administrator Features
- **User Management**: Complete CRUD operations for all user types (admins, supervisors, researchers, students)
- **System Dashboard**: Real-time statistics showing user counts and thesis distribution
- **Thesis Overview**: Comprehensive view of all assigned and available theses
- **Research Project Monitoring**: Overview of research projects and collaborations
- **Supervisor Role Management**: Grant and revoke supervisor privileges to researchers
- **Email Notification Management**: Configure and manage weekly supervisor email reports
- **Activity Monitoring**: Track user activity across the platform
- **Scheduler Management**: Monitor and control background task scheduling
- **Email Testing**: Preview and test weekly notification emails before sending
- **Data Export**: JSON and CSV export capabilities for system data
- **System Health Monitoring**: Built-in health checks and system diagnostics

### 🔬 Researcher Features (NEW!)
- **Research Project Management**: Create, update, and delete research projects
- **Collaboration System**: Invite other researchers as collaborators with different roles
- **Project Dashboard**: Overview of personal research projects and statistics
- **Dual Role Support**: Access supervisor functions when granted supervisor privileges
- **Collaborative Workspace**: Share projects with team members and manage permissions
- **Progress Tracking**: Monitor research project milestones and activities

### 👨‍🏫 Supervisor Features
- **Student Management**: View and manage supervised students with activity tracking
- **Thesis Supervision**: Track thesis progress and provide feedback
- **Resource Sharing**: Upload and manage thesis-related resources
- **Progress Monitoring**: Track student updates and milestones
- **Weekly Email Reports**: Automatic Monday morning activity summaries for all supervised students
- **Activity Status Indicators**: Visual indicators for active/inactive students with last activity locations
- **Inactive Student Alerts**: Clear highlighting of students inactive for more than 2 weeks
- **Profile Management**: Update personal information and preferences

### 👨‍🎓 Student Features
- **Personal Dashboard**: Overview of thesis status and recent activities
- **Thesis Details**: View thesis description, requirements, and supervisor information
- **Progress Tracking**: Submit updates and track thesis milestones
- **Resource Access**: Download supervisor-provided resources and materials
- **Profile Management**: Update personal information and account settings

## 📧 Notification System

SuperviseMe includes comprehensive notification systems to keep users informed about thesis activities and important updates.

### 🔔 Telegram Notifications (NEW!)

Real-time notifications delivered directly to your Telegram account:

- **Instant Delivery**: Immediate notifications for urgent activities
- **Customizable Types**: Choose which notifications to receive via Telegram
- **Rich Formatting**: Formatted messages with emojis and action links
- **Secure Setup**: Verified user identification prevents impersonation
- **Multi-Channel**: Works alongside email notifications

**Available Notification Types:**
- 📝 New thesis updates from students
- 💬 Supervisor feedback and comments
- ✅ Task assignments and completions
- 📊 Thesis status changes
- ⏰ Deadline reminders
- 📈 Weekly activity summaries

See [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) for detailed setup instructions.

### 📧 Weekly Email System

Automated weekly email reports for supervisors:

- **Automated Schedule**: Weekly reports are automatically sent every Monday morning at 9:00 AM
- **Activity Summary**: Each supervisor receives a detailed summary of all supervised students' weekly activities
- **Inactive Student Alerts**: Students who have been inactive for more than 2 weeks are clearly highlighted
- **Last Activity Tracking**: Shows where students were last active on the platform (e.g., "student_dashboard", "posting_thesis_update")
- **Update Statistics**: Number of thesis updates posted by each student during the past week
- **Professional Templates**: Clean, easy-to-read email format with structured information

### 📊 Activity Monitoring

The system continuously tracks student engagement:
- **Login Activity**: Records when students access their dashboards
- **Update Posts**: Tracks when students post thesis progress updates
- **Platform Interaction**: Monitors various forms of student engagement
- **Location Tracking**: Records which part of the platform students were using

### ⚙️ Administrative Control

Administrators have full control over the email notification system:
- **Scheduler Status**: Monitor the background task scheduler status
- **Email Testing**: Preview weekly reports for any supervisor before sending
- **Manual Triggers**: Send weekly reports immediately for testing purposes
- **Schedule Management**: Monitor next run times and job configurations

### 🎯 Benefits

- **Proactive Supervision**: Supervisors are automatically notified of inactive students
- **Improved Communication**: Regular updates keep everyone informed
- **Early Intervention**: Identify struggling students before issues become critical
- **Professional Workflow**: Automated system reduces manual oversight burden

### 🗄️ Data Management
- **SQLite Database**: Lightweight, file-based database for development and small deployments
- **PostgreSQL Support**: Enterprise-grade database support for production environments
- **Sample Data**: Pre-configured sample users and theses for testing and demonstration
- **Data Integrity**: Proper foreign key relationships and cascade operations

## 🚀 Installation & Setup

### Quick Start (Local Development)

#### Prerequisites
- Python 3.8+
- pip (Python package installer)
- (Optional) PostgreSQL for production deployment

#### Local Installation

1. **Clone the repository**
```bash
git clone https://github.com/GiulioRossetti/SuperviseMe.git
cd SuperviseMe
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **(Optional) Configure seed passwords**
```bash
export ADMIN_BOOTSTRAP_PASSWORD=change-me-admin
export SEED_DEFAULT_PASSWORD=change-me-seed
# Or set role-specific values:
# export SEED_SUPERVISOR_PASSWORD=...
# export SEED_STUDENT_PASSWORD=...
# export SEED_RESEARCHER_PASSWORD=...
```

4. **Initialize the database with sample data**
```bash
python seed_database.py
```

5. **Run database migrations (for existing installations)**
```bash
# If upgrading from a previous version, run migrations to add new features
python migrate_database.py      # For activity tracking
python migrate_telegram.py      # For Telegram notifications (NEW!)
python migrate_researcher.py    # For researcher role and research projects (NEW!)
```

6. **Configure Telegram notifications (optional)**
   - See [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) for detailed setup instructions
   - Create a Telegram bot via @BotFather
   - Configure bot settings in the admin panel

7. **Start the application**
```bash
python superviseme.py
```

8. **Access the application**
Open your web browser and navigate to `http://localhost:8080`

### 🐳 Docker Setup (Recommended)

For a complete production-ready setup with database persistence, SSL, and mail server:

#### Prerequisites
- Docker and Docker Compose installed on your system

#### Quick Start with Docker

1. **Clone and navigate to the repository**:
   ```bash
   git clone https://github.com/GiulioRossetti/SuperviseMe.git
   cd SuperviseMe
   ```

2. **Create environment configuration**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and customize the values, especially:
   - `SECRET_KEY`: Use a strong, unique secret key
   - `ADMIN_BOOTSTRAP_PASSWORD`: Set a strong admin bootstrap password
   - `PG_PASSWORD`: Set a secure database password

3. **Provide TLS files for Nginx**:
   - Place certificate and key files in `nginx/ssl/`:
     - `superviseme.crt`
     - `superviseme.key`

4. **Start the application**:
   ```bash
   docker-compose up -d
   ```

5. **Access the application**:
   - Main application: https://localhost
   - Mail server UI: http://localhost:8025

#### Docker Architecture

The Docker setup includes:
- **superviseme_app**: Flask application running with Gunicorn
- **postgres**: PostgreSQL database with persistent storage
- **nginx**: Reverse proxy with SSL termination and static file serving
- **mailhog**: Development mail server for testing email functionality

#### Development Mode with Docker

For development with hot reloading:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Development features:
- Flask development server with auto-reload
- Source code volume mounting
- Debug mode enabled
- Direct access to application on port 8080

#### Data Persistence

**Database Data**
- Volume: `postgres_data`
- Backup: `docker-compose exec postgres pg_dump -U superviseme_user superviseme > backup.sql`

**Application Data**
- Volume: `app_data`
- Purpose: Persistent storage for SQLite fallback and file uploads

For detailed Docker setup instructions, see [DOCKER_README.md](DOCKER_README.md).

### Advanced Configuration

#### Database Configuration

**SQLite (Default - Development)**
```bash
python superviseme.py --db sqlite
```

**PostgreSQL (Production)**
```bash
# Set environment variables
export PG_USER=your_username
export PG_PASSWORD=your_password  
export PG_HOST=localhost
export PG_PORT=5432
export PG_DBNAME=superviseme

# Run with PostgreSQL
python superviseme.py --db postgresql
```

#### Command Line Options
```bash
python superviseme.py --help

Options:
  -x, --host TEXT        Host address to run the app on (default: localhost)
  -y, --port TEXT        Port to run the app on (default: 8080)
  -d, --debug           Enable debug mode
  -D, --db [sqlite|postgresql]  Database type (default: sqlite)
```

## 👥 Sample Data & Test Credentials

The application comes pre-configured with sample data for immediate testing and demonstration:

### 🔑 Test Login Credentials

Password values depend on your environment configuration:
- `ADMIN_BOOTSTRAP_PASSWORD` for admin bootstrap user
- `SEED_SUPERVISOR_PASSWORD` / `SEED_STUDENT_PASSWORD` / `SEED_RESEARCHER_PASSWORD`
- If role-specific seed password is not set, `SEED_DEFAULT_PASSWORD` is used
- If none are set, seed script falls back to `test` (development fallback only)

#### Administrator Account
- **Email**: `admin@supervise.me`
- **Password**: value from `ADMIN_BOOTSTRAP_PASSWORD`
- **Role**: System Administrator
- **Access**: Full system access, user management, system statistics

#### Supervisor Accounts
- **Email**: `j.smith@university.edu`
- **Email**: `e.johnson@university.edu`  
- **Email**: `m.garcia@university.edu`
- **Password**: `SEED_SUPERVISOR_PASSWORD` (or `SEED_DEFAULT_PASSWORD`)
- **Role**: Thesis Supervisors
- **Access**: Student supervision, thesis management, resource sharing

#### Researcher Accounts (NEW!)
- **Email**: `alice.johnson@university.edu`
  - **Special Role**: Also has supervisor privileges
  - **Access**: Research project management + thesis supervision
- **Email**: `bob.williams@university.edu`
  - **Role**: Researcher only
  - **Access**: Research project management and collaboration
- **Email**: `maria.rodriguez@university.edu`
  - **Special Role**: Also has supervisor privileges
  - **Access**: Research project management + thesis supervision
- **Password**: `SEED_RESEARCHER_PASSWORD` (or `SEED_DEFAULT_PASSWORD`)

#### Student Accounts
- **Email**: `alice.doe@student.university.edu`
- **Email**: `bob.wilson@student.university.edu`
- **Email**: `carol.brown@student.university.edu`
- **Email**: `david.miller@student.university.edu`
- **Email**: `eva.clark@student.university.edu`
- **Password**: `SEED_STUDENT_PASSWORD` (or `SEED_DEFAULT_PASSWORD`)
- **Role**: Students
- **Access**: Personal dashboard, thesis tracking, progress updates

### 📊 Sample Theses Data

The system includes 7 sample theses across different academic levels:

#### Assigned Theses (5)
1. **Machine Learning for Predictive Analytics in Healthcare** (Alice Doe - Master's)
2. **Deep Learning Approaches for Natural Language Processing** (Bob Wilson - Bachelor's)
3. **Computer Vision for Autonomous Vehicle Navigation** (David Miller - Master's)
4. **Quantum Computing Applications in Cryptography** (Eva Clark - Bachelor's)
5. **Blockchain Technology in Supply Chain Management** (Carol Brown - Master's)

#### Available Theses (2)
1. **IoT Security Framework for Smart Cities** (Other level)
2. **AI-Driven Personalized Learning Systems** (Bachelor's level)

### 🔬 Sample Research Projects Data (NEW!)

The system includes 4 sample research projects with collaborations:

#### Research Projects
1. **Machine Learning for Climate Prediction** (Dr. Alice Johnson - Research level)
   - **Collaborator**: Dr. Bob Williams (Co-investigator)
2. **Social Network Analysis in Online Communities** (Dr. Bob Williams - Full-scale)
   - **Collaborator**: Dr. Maria Rodriguez (Collaborator)
3. **Ethics in Artificial Intelligence Systems** (Dr. Maria Rodriguez - Longitudinal)
   - **Collaborator**: Dr. Alice Johnson (Advisor)
4. **Quantum Computing Applications in Healthcare** (Dr. Alice Johnson - Pilot)

#### Collaboration Features
- **Role-Based Collaboration**: Different collaboration roles (collaborator, co-investigator, advisor)
- **Cross-Project Collaboration**: Researchers can collaborate on multiple projects
- **Access Control**: Project owners can add/remove collaborators

## 📱 User Interface Screenshots

### 🔐 Login Interface
![Login Page](https://github.com/user-attachments/assets/14d6b4b7-6a67-4c0c-91fa-0020c9927aff)

The login page features a clean, modern design with:
- Email and password authentication
- Remember me functionality
- Responsive layout that adapts to different screen sizes
- Clear error messaging for failed login attempts

### 👨‍💼 Administrator Dashboard
![Admin Dashboard with Researchers](admin-dashboard-with-researchers.png)

The administrator dashboard provides:
- **System Statistics**: Real-time counts of admins, supervisors, researchers, students, and theses
- **Assigned Theses Table**: Complete overview of all active thesis assignments
- **Available Theses Table**: List of theses available for assignment
- **Navigation Menu**: Quick access to user management, thesis management, and system tools

### 👨‍💼 Administrator User Management
![Admin Users with Researchers](admin-users-with-researchers.png)

The user management interface shows:
- **Complete User List**: All users across different roles including researchers
- **Role-Based Filtering**: Easy identification of different user types
- **Create User Form**: Includes researcher role option in the dropdown
- **User Actions**: Direct access to user details and deletion functions

### 🔬 Researcher Dashboard (With Supervisor Access)
*Screenshot showing researcher dashboard with both research projects and supervisor access panel*

The researcher dashboard features:
- **Research Project Statistics**: Overview of personal research projects
- **Supervised Theses Count**: Shows supervised theses when user has supervisor privileges
- **Recent Projects Table**: Quick access to research projects with status and collaboration info
- **Dual Navigation**: Both research and supervision menu sections when applicable
- **Supervisor Functions**: Quick access panel to supervisor tools when privileges are granted

### 🔬 Researcher Project Management
*Screenshot showing research project management interface with collaborations*

The research project management interface provides:
- **Project Overview Table**: Complete list of research projects with descriptions, levels, and collaborators
- **Collaboration Status**: Visual indicators showing project collaborators and their roles
- **Project Actions**: Edit, delete, and view options for each project
- **Create Project Modal**: Easy project creation with title, description, and level selection
- **Collaborator Management**: Add/remove collaborators with different role assignments

### 🔬 Researcher Dashboard (Researcher Only)
*Screenshot showing researcher dashboard without supervisor privileges*

For researchers without supervisor privileges:
- **Research-Focused Interface**: Clean dashboard focusing on research activities
- **Project Statistics**: Personal research project metrics and collaboration counts
- **Simplified Navigation**: Research-only menu without supervisor functions
- **Collaboration Overview**: Shows projects where user is a collaborator

### 👨‍🎓 Student Dashboard
![Student Dashboard](https://github.com/user-attachments/assets/2fa0923e-7984-4251-8449-023be3643757)

The student dashboard features:
- **Personal Statistics**: Overview of updates, feedback, resources, and thesis status
- **My Thesis Section**: Detailed view of assigned thesis with description and metadata
- **Recent Updates Section**: Timeline of thesis progress and activities
- **Navigation Menu**: Access to thesis details, progress tracking, and profile management

### 🔓 Logout Functionality
![Logout Redirect](https://github.com/user-attachments/assets/42e154f8-f4a1-471f-b6fd-20ba5fa2fead)

Secure logout implementation:
- Proper session cleanup and termination
- Automatic redirect to login page
- Clean interface return for new login attempts

## 🏗️ Technical Architecture

### Backend Framework
- **Flask**: Lightweight and flexible Python web framework
- **Flask-SQLAlchemy**: ORM for database operations
- **Flask-Login**: User session management and authentication
- **Flask-Mail**: Email functionality for weekly notifications
- **APScheduler**: Background task scheduling for automated emails
- **Werkzeug**: Password hashing and security utilities

### Database Schema
- **Users**: Administrators, supervisors, researchers, and students with role-based permissions and activity tracking
- **Theses**: Thesis information, descriptions, and metadata  
- **Thesis-Supervisor Relationships**: Many-to-many relationships between theses and supervisors
- **Thesis Status**: Current status tracking (Active, Completed, etc.)
- **Thesis Tags**: Categorization and organization system
- **Research Projects**: Research project information, descriptions, and researcher ownership
- **Research Collaborations**: Many-to-many relationships between research projects and collaborating researchers
- **Supervisor Roles**: Role grants allowing researchers to access supervisor functions
- **Activity Tracking**: User activity monitoring with timestamps and location tracking

### Frontend Technologies
- **HTML5/CSS3**: Modern, semantic markup and responsive styling
- **Bootstrap**: Responsive grid system and UI components
- **JavaScript**: Interactive features and AJAX functionality
- **Font Awesome**: Icon system for intuitive navigation

### Security Features
- **Password Hashing**: PBKDF2-SHA256 encryption for user passwords
- **Session Management**: Secure Flask sessions with CSRF protection
- **Input Validation**: Server-side validation for all user inputs
- **Role-Based Authorization**: Route-level access control based on user roles

## 🔧 Development Features

### Database Management
```bash
# Initialize fresh database with all sample data (including researchers)
python seed_database.py

# The seed script will:
# - Clear existing data
# - Create admin, supervisor, researcher, and student accounts
# - Generate sample theses and relationships
# - Create sample research projects and collaborations
# - Grant supervisor roles to selected researchers
# - Set up proper foreign key constraints
```

### Local Quality Gates
```bash
# Run lint + compile + schema alignment + tests
make ci

# Run smoke checks against a local server process
make smoke
```

### Migration Scripts
For existing installations, run these migration scripts in order:
```bash
# Core system migrations
python migrate_database.py      # For activity tracking
python migrate_telegram.py      # For Telegram notifications
python migrate_researcher.py    # For researcher role and research projects (NEW!)

# The researcher migration will:
# - Add researcher user accounts
# - Create research project and collaboration tables
# - Set up supervisor role management
# - Add sample research data for testing
```

### API Endpoints
The application includes several API endpoints for data access:
- `/admin/api/system_stats` - System statistics and metrics
- `/admin/api/export_data` - JSON export of system data
- `/admin/api/export_data/csv` - CSV export with ZIP delivery

### Debugging and Development
- **Debug Mode**: Detailed error messages and auto-reload functionality
- **Logging**: Comprehensive logging for troubleshooting
- **Sample Data**: Pre-configured test environment for development

## 🚀 Production Deployment

### Environment Variables
```bash
export FLASK_ENV=production
export SECRET_KEY=your-secret-key-here
export ADMIN_BOOTSTRAP_PASSWORD=your-bootstrap-password
export ENABLE_SCHEDULER=false
export SKIP_DB_SEED=true

# Database Configuration
export PG_USER=your_db_user
export PG_PASSWORD=your_db_password
export PG_HOST=your_db_host
export PG_PORT=5432
export PG_DBNAME=superviseme_production

# Email Configuration (required for weekly notifications)
export MAIL_SERVER=smtp.gmail.com
export MAIL_PORT=587
export MAIL_USE_TLS=true
export MAIL_USE_SSL=false
export MAIL_USERNAME=your-email@gmail.com
export MAIL_PASSWORD=your-app-password
export MAIL_DEFAULT_SENDER=your-email@gmail.com
```

### Deployment Operations
- Use `ENABLE_SCHEDULER=true` in exactly one scheduler worker/service only.
- Keep all web replicas on `ENABLE_SCHEDULER=false`.
- Follow the full operational checklist in `/DEPLOYMENT_RUNBOOK.md`.

### CI Quality Gates
CI runs on push and pull request with:
- `ruff` runtime-safety lint rules
- Python compile checks
- Schema alignment verification (`scripts/check_schema_alignment.py`)
- Automated tests (`pytest`)

### WSGI Configuration
For production deployment with gunicorn or similar WSGI servers:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 superviseme:app
```

## 📁 Project Structure

```
SuperviseMe/
├── superviseme/                 # Main application package
│   ├── __init__.py             # Application factory and configuration
│   ├── models.py               # Database models and relationships
│   ├── routes/                 # Route handlers organized by functionality
│   │   ├── auth.py             # Authentication routes (login/logout)
│   │   ├── admin.py            # Administrator dashboard and management
│   │   ├── supervisor.py       # Supervisor dashboard and tools  
│   │   ├── researcher.py       # Researcher dashboard and project management (NEW!)
│   │   ├── student.py          # Student dashboard and features
│   │   └── profile.py          # User profile management
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── login.html          # Authentication interface
│   │   ├── admin/              # Administrator interface templates
│   │   ├── supervisor/         # Supervisor interface templates
│   │   ├── researcher/         # Researcher interface templates (NEW!)
│   │   └── student/            # Student interface templates
│   ├── static/                 # Static assets (CSS, JS, images)
│   │   └── assets/             # Bootstrap and custom assets
│   └── utils/                  # Utility functions and helpers
├── data_schema/                # Database schema and initialization
├── seed_database.py            # Sample data generation script (enhanced with researchers)
├── scripts/
│   └── check_schema_alignment.py # Schema vs models consistency check
├── Makefile                    # Local CI/smoke command shortcuts
├── migrate_researcher.py       # Migration script for researcher functionality (NEW!)
├── DEPLOYMENT_RUNBOOK.md       # Production rollout/rollback/smoke procedures
├── superviseme.py              # Application entry point
├── requirements.txt            # Python dependencies
└── README.md                   # This documentation
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🙋‍♂️ Support

For questions, issues, or contributions, please:
- Open an issue on GitHub
- Contact the development team
- Review the documentation and sample configurations

---

**SuperviseMe** - Streamlining thesis supervision and research collaboration for the modern academic environment.
