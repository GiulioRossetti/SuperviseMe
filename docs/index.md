# SuperviseMe

SuperviseMe is a comprehensive web application for thesis supervision and research project management in academic environments. It streamlines the process of thesis supervision by providing dedicated dashboards for administrators, supervisors, researchers, and students, along with robust user management and project tracking capabilities.

## 🎯 Project Overview

SuperviseMe is a Flask-based web application designed to facilitate thesis supervision and research collaboration in universities and academic institutions. The platform provides role-based access control with distinct interfaces for administrators, supervisors, researchers, and students, each tailored to their specific needs and responsibilities.

## ✨ Key Features

### 🔐 Authentication & Authorization
- **Secure Login System**: Email-based authentication with password hashing using PBKDF2-SHA256
- **Role-Based Access Control**: Separate dashboards and permissions for admins, supervisors, researchers, and students
- **Session Management**: Secure session handling with remember-me functionality
- **Logout Protection**: Proper session cleanup and redirect handling
- **Social Login**: Support for Google and ORCID login

### 👨‍💼 Administrator Features
- **User Management**: Complete CRUD operations for all user types
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

### 🔬 Researcher Features
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
- **Activity Status Indicators**: Visual indicators for active/inactive students
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

### 🔔 Telegram Notifications

Real-time notifications delivered directly to your Telegram account:
- **Instant Delivery**: Immediate notifications for urgent activities
- **Customizable Types**: Choose which notifications to receive via Telegram
- **Rich Formatting**: Formatted messages with emojis and action links
- **Secure Setup**: Verified user identification prevents impersonation
- **Multi-Channel**: Works alongside email notifications

See [Telegram Setup](telegram_setup.md) for detailed instructions.

### 📧 Weekly Email System

Automated weekly email reports for supervisors:
- **Automated Schedule**: Weekly reports sent every Monday morning at 9:00 AM
- **Activity Summary**: Detailed summary of all supervised students' weekly activities
- **Inactive Student Alerts**: Highlighting of students inactive for more than 2 weeks
- **Professional Templates**: Clean, easy-to-read email format with structured information

## 🏗️ Technical Architecture

### Backend Framework
- **Flask**: Lightweight and flexible Python web framework
- **Flask-SQLAlchemy**: ORM for database operations
- **Flask-Login**: User session management and authentication
- **Flask-Mail**: Email functionality for weekly notifications
- **APScheduler**: Background task scheduling for automated emails
- **Werkzeug**: Password hashing and security utilities
- **Authlib**: OAuth integration for social logins

### Database Schema
- **Users**: Administrators, supervisors, researchers, and students with role-based permissions
- **Theses**: Thesis information, descriptions, and metadata
- **Thesis-Supervisor Relationships**: Many-to-many relationships
- **Thesis Status**: Current status tracking (Active, Completed, etc.)
- **Research Projects**: Research project information
- **Research Collaborations**: Many-to-many relationships between research projects and researchers
- **Activity Tracking**: User activity monitoring with timestamps and location tracking

### Frontend Technologies
- **HTML5/CSS3**: Modern, semantic markup and responsive styling
- **Bootstrap**: Responsive grid system and UI components
- **JavaScript**: Interactive features and AJAX functionality
- **Font Awesome**: Icon system for intuitive navigation

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](https://github.com/GiulioRossetti/SuperviseMe/blob/main/LICENSE) file for details.
