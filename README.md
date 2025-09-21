# SuperviseMe

A comprehensive web application for thesis supervision and management in academic environments. SuperviseMe streamlines the process of thesis supervision by providing dedicated dashboards for administrators, supervisors, and students, along with robust user management and thesis tracking capabilities.

## 🎯 Project Overview

SuperviseMe is a Flask-based web application designed to facilitate thesis supervision in universities and academic institutions. The platform provides role-based access control with distinct interfaces for administrators, supervisors, and students, each tailored to their specific needs and responsibilities.

## ✨ Key Features

### 🔐 Authentication & Authorization
- **Secure Login System**: Email-based authentication with password hashing using PBKDF2-SHA256
- **Role-Based Access Control**: Separate dashboards and permissions for admins, supervisors, and students
- **Session Management**: Secure session handling with remember-me functionality
- **Logout Protection**: Proper session cleanup and redirect handling

### 👨‍💼 Administrator Features
- **User Management**: Complete CRUD operations for all user types (admins, supervisors, students)
- **System Dashboard**: Real-time statistics showing user counts and thesis distribution
- **Thesis Overview**: Comprehensive view of all assigned and available theses
- **Email Notification Management**: Configure and manage weekly supervisor email reports
- **Activity Monitoring**: Track user activity across the platform
- **Scheduler Management**: Monitor and control background task scheduling
- **Email Testing**: Preview and test weekly notification emails before sending
- **Data Export**: JSON and CSV export capabilities for system data
- **System Health Monitoring**: Built-in health checks and system diagnostics

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

## 📧 Weekly Email Notification System

SuperviseMe includes a comprehensive weekly email notification system that keeps supervisors informed about their students' activities and engagement levels.

### ✨ Email Report Features

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

### Prerequisites
- Python 3.8+
- pip (Python package installer)
- (Optional) PostgreSQL for production deployment

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/GiulioRossetti/SuperviseMe.git
cd SuperviseMe
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Initialize the database with sample data**
```bash
python seed_database.py
```

4. **Run database migration (for existing installations)**
```bash
# If upgrading from a previous version, run migration to add activity tracking
python migrate_database.py
```

5. **Start the application**
```bash
python superviseme.py
```

6. **Access the application**
Open your web browser and navigate to `http://localhost:8080`

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

#### Administrator Account
- **Email**: `admin@supervise.me`
- **Password**: `test`
- **Role**: System Administrator
- **Access**: Full system access, user management, system statistics

#### Supervisor Accounts
- **Email**: `j.smith@university.edu` | **Password**: `supervisor123`
- **Email**: `e.johnson@university.edu` | **Password**: `supervisor123`  
- **Email**: `m.garcia@university.edu` | **Password**: `supervisor123`
- **Role**: Thesis Supervisors
- **Access**: Student supervision, thesis management, resource sharing

#### Student Accounts
- **Email**: `alice.doe@student.university.edu` | **Password**: `student123`
- **Email**: `bob.wilson@student.university.edu` | **Password**: `student123`
- **Email**: `carol.brown@student.university.edu` | **Password**: `student123`
- **Email**: `david.miller@student.university.edu` | **Password**: `student123`
- **Email**: `eva.clark@student.university.edu` | **Password**: `student123`
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

## 📱 User Interface Screenshots

### 🔐 Login Interface
![Login Page](https://github.com/user-attachments/assets/14d6b4b7-6a67-4c0c-91fa-0020c9927aff)

The login page features a clean, modern design with:
- Email and password authentication
- Remember me functionality
- Responsive layout that adapts to different screen sizes
- Clear error messaging for failed login attempts

### 👨‍💼 Administrator Dashboard
![Admin Dashboard](https://github.com/user-attachments/assets/882874cd-9b5b-4ae9-a53c-90a950b138a7)

The administrator dashboard provides:
- **System Statistics**: Real-time counts of admins, supervisors, students, and theses
- **Assigned Theses Table**: Complete overview of all active thesis assignments
- **Available Theses Table**: List of theses available for assignment
- **Navigation Menu**: Quick access to user management, thesis management, and system tools

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
- **Users**: Administrators, supervisors, and students with role-based permissions and activity tracking
- **Theses**: Thesis information, descriptions, and metadata  
- **Thesis-Supervisor Relationships**: Many-to-many relationships between theses and supervisors
- **Thesis Status**: Current status tracking (Active, Completed, etc.)
- **Thesis Tags**: Categorization and organization system
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
# Initialize fresh database
python seed_database.py

# The seed script will:
# - Clear existing data
# - Create admin, supervisor, and student accounts
# - Generate sample theses and relationships
# - Set up proper foreign key constraints
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
│   │   ├── student.py          # Student dashboard and features
│   │   └── profile.py          # User profile management
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── login.html          # Authentication interface
│   │   ├── admin/              # Administrator interface templates
│   │   ├── supervisor/         # Supervisor interface templates
│   │   └── student/            # Student interface templates
│   ├── static/                 # Static assets (CSS, JS, images)
│   │   └── assets/             # Bootstrap and custom assets
│   └── utils/                  # Utility functions and helpers
├── data_schema/                # Database schema and initialization
├── seed_database.py            # Sample data generation script
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

**SuperviseMe** - Streamlining thesis supervision for the modern academic environment.