"""
Weekly email notification service for SuperviseMe application
"""
from flask import current_app, render_template_string
from superviseme.utils.email_service import send_email
from superviseme.utils.activity_tracker import get_weekly_activity_summary
from superviseme.models import User_mgmt, Thesis_Supervisor
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def send_weekly_supervisor_report(supervisor_id):
    """
    Send a weekly activity report to a specific supervisor
    
    Args:
        supervisor_id (int): ID of the supervisor to send the report to
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        supervisor = User_mgmt.query.get(supervisor_id)
        if not supervisor or supervisor.user_type != 'supervisor':
            logger.error(f"Invalid supervisor ID: {supervisor_id}")
            return False
        
        # Get activity summary for this supervisor
        activity_summary = get_weekly_activity_summary(supervisor_id)
        
        # Skip sending email if no students
        if activity_summary['total_students'] == 0:
            logger.info(f"No students found for supervisor {supervisor.username}, skipping email")
            return True
        
        # Prepare email content
        subject = f"Weekly Student Activity Report - {datetime.now().strftime('%B %d, %Y')}"
        
        email_template = """
Dear {{ supervisor_name }},

Here is your weekly student activity report for the week of {{ report_date }}:

SUMMARY:
========
Total Students: {{ total_students }}
Active Students: {{ active_students }}
Inactive Students (>2 weeks): {{ inactive_students }}
Total Updates This Week: {{ total_updates }}

STUDENT DETAILS:
================
{% for student_info in students %}
• {{ student_info.student.name }} {{ student_info.student.surname }}
  Thesis: {{ student_info.thesis.title }}
  Updates this week: {{ student_info.recent_updates }}
  {% if student_info.is_inactive %}
  ⚠️  INACTIVE for {{ student_info.days_since_activity }} days
  {% if student_info.last_activity_location %}
  Last seen: {{ student_info.last_activity_location }}
  {% else %}
  Last seen: Unknown
  {% endif %}
  {% else %}
  ✅ Active
  {% if student_info.last_activity_location %}
  Last seen: {{ student_info.last_activity_location }}
  {% endif %}
  {% endif %}

{% endfor %}

{% if inactive_students > 0 %}
ATTENTION REQUIRED:
==================
You have {{ inactive_students }} student(s) who have been inactive for more than 2 weeks. 
Please consider reaching out to these students to check on their progress.
{% endif %}

To view more details, please log in to your SuperviseMe dashboard.

Best regards,
SuperviseMe System

---
This is an automated weekly report sent every Monday morning.
"""
        
        # Render the template
        email_body = render_template_string(
            email_template,
            supervisor_name=f"{supervisor.name} {supervisor.surname}",
            report_date=datetime.now().strftime('%B %d, %Y'),
            total_students=activity_summary['total_students'],
            active_students=activity_summary['active_students'],
            inactive_students=activity_summary['inactive_students'],
            total_updates=activity_summary['total_updates_this_week'],
            students=activity_summary['students']
        )
        
        # Send the email
        success = send_email(subject, supervisor.email, email_body)
        
        if success:
            logger.info(f"Weekly report sent successfully to {supervisor.email}")
        else:
            logger.error(f"Failed to send weekly report to {supervisor.email}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error sending weekly report to supervisor {supervisor_id}: {str(e)}")
        return False


def send_all_weekly_supervisor_reports():
    """
    Send weekly reports to all supervisors who have active students
    
    Returns:
        dict: Summary of email sending results
    """
    try:
        # Get all supervisors
        supervisors = User_mgmt.query.filter_by(user_type='supervisor').all()
        
        results = {
            'total_supervisors': len(supervisors),
            'emails_sent': 0,
            'emails_failed': 0,
            'supervisors_with_students': 0,
            'supervisors_without_students': 0
        }
        
        for supervisor in supervisors:
            # Check if supervisor has any students
            has_students = Thesis_Supervisor.query.filter_by(supervisor_id=supervisor.id).first() is not None
            
            if has_students:
                results['supervisors_with_students'] += 1
                success = send_weekly_supervisor_report(supervisor.id)
                if success:
                    results['emails_sent'] += 1
                else:
                    results['emails_failed'] += 1
            else:
                results['supervisors_without_students'] += 1
                logger.info(f"Supervisor {supervisor.username} has no students, skipping email")
        
        logger.info(f"Weekly report batch completed: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error in send_all_weekly_supervisor_reports: {str(e)}")
        return {'error': str(e)}


# Template for testing individual supervisor reports
def preview_weekly_supervisor_report(supervisor_id):
    """
    Generate a preview of the weekly report for testing purposes
    
    Args:
        supervisor_id (int): ID of the supervisor
    
    Returns:
        dict: Preview data including email subject and body
    """
    try:
        supervisor = User_mgmt.query.get(supervisor_id)
        if not supervisor:
            return {'error': 'Supervisor not found'}
        
        activity_summary = get_weekly_activity_summary(supervisor_id)
        
        subject = f"Weekly Student Activity Report - {datetime.now().strftime('%B %d, %Y')}"
        
        email_template = """
Dear {{ supervisor_name }},

Here is your weekly student activity report for the week of {{ report_date }}:

SUMMARY:
========
Total Students: {{ total_students }}
Active Students: {{ active_students }}
Inactive Students (>2 weeks): {{ inactive_students }}
Total Updates This Week: {{ total_updates }}

STUDENT DETAILS:
================
{% for student_info in students %}
• {{ student_info.student.name }} {{ student_info.student.surname }}
  Thesis: {{ student_info.thesis.title }}
  Updates this week: {{ student_info.recent_updates }}
  {% if student_info.is_inactive %}
  ⚠️  INACTIVE for {{ student_info.days_since_activity }} days
  {% if student_info.last_activity_location %}
  Last seen: {{ student_info.last_activity_location }}
  {% else %}
  Last seen: Unknown
  {% endif %}
  {% else %}
  ✅ Active
  {% if student_info.last_activity_location %}
  Last seen: {{ student_info.last_activity_location }}
  {% endif %}
  {% endif %}

{% endfor %}

{% if inactive_students > 0 %}
ATTENTION REQUIRED:
==================
You have {{ inactive_students }} student(s) who have been inactive for more than 2 weeks. 
Please consider reaching out to these students to check on their progress.
{% endif %}

To view more details, please log in to your SuperviseMe dashboard.

Best regards,
SuperviseMe System

---
This is an automated weekly report sent every Monday morning.
"""
        
        email_body = render_template_string(
            email_template,
            supervisor_name=f"{supervisor.name} {supervisor.surname}",
            report_date=datetime.now().strftime('%B %d, %Y'),
            total_students=activity_summary['total_students'],
            active_students=activity_summary['active_students'],
            inactive_students=activity_summary['inactive_students'],
            total_updates=activity_summary['total_updates_this_week'],
            students=activity_summary['students']
        )
        
        return {
            'subject': subject,
            'body': email_body,
            'recipient': supervisor.email,
            'activity_summary': activity_summary
        }
        
    except Exception as e:
        logger.error(f"Error generating preview for supervisor {supervisor_id}: {str(e)}")
        return {'error': str(e)}