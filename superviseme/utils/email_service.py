"""
Email service utilities for SuperviseMe application
"""
from flask import current_app, render_template_string
from flask_mail import Message
from superviseme import mail
import logging

logger = logging.getLogger(__name__)


def send_email(subject, recipients, text_body, html_body=None, sender=None):
    """
    Send an email using Flask-Mail
    
    Args:
        subject (str): Email subject
        recipients (list): List of recipient email addresses
        text_body (str): Plain text email content
        html_body (str, optional): HTML email content
        sender (str, optional): Sender email address
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        if sender is None:
            sender = current_app.config.get('MAIL_DEFAULT_SENDER')
        
        msg = Message(
            subject=subject,
            sender=sender,
            recipients=recipients if isinstance(recipients, list) else [recipients]
        )
        msg.body = text_body
        if html_body:
            msg.html = html_body
        
        mail.send(msg)
        logger.info(f"Email sent successfully to {recipients}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipients}: {str(e)}")
        return False


def send_notification_email(user_email, notification_type, **kwargs):
    """
    Send notification emails for various events
    
    Args:
        user_email (str): Recipient email address
        notification_type (str): Type of notification
        **kwargs: Additional context variables for the email template
    """
    templates = {
        'thesis_assigned': {
            'subject': 'New Thesis Assigned - SuperviseMe',
            'template': """
Hello {{ user_name }},

You have been assigned a new thesis to supervise:

Title: {{ thesis_title }}
Student: {{ student_name }}
Level: {{ thesis_level }}

Please log in to SuperviseMe to review the details.

Best regards,
SuperviseMe System
            """
        },
        'thesis_submitted': {
            'subject': 'Thesis Submitted for Review - SuperviseMe',
            'template': """
Hello {{ supervisor_name }},

A thesis has been submitted for your review:

Title: {{ thesis_title }}
Student: {{ student_name }}
Submitted: {{ submission_date }}

Please log in to SuperviseMe to review the submission.

Best regards,
SuperviseMe System
            """
        },
        'status_update': {
            'subject': 'Thesis Status Update - SuperviseMe',
            'template': """
Hello {{ user_name }},

The status of your thesis has been updated:

Title: {{ thesis_title }}
New Status: {{ new_status }}
Updated by: {{ updated_by }}

Please log in to SuperviseMe for more details.

Best regards,
SuperviseMe System
            """
        }
    }
    
    if notification_type not in templates:
        logger.error(f"Unknown notification type: {notification_type}")
        return False
    
    template_config = templates[notification_type]
    subject = template_config['subject']
    text_body = render_template_string(template_config['template'], **kwargs)
    
    return send_email(subject, user_email, text_body)


def test_email_connection():
    """
    Test email server connection
    
    Returns:
        dict: Connection test results
    """
    try:
        with mail.connect() as conn:
            logger.info("Email connection test successful")
            return {'success': True, 'message': 'Email server connection successful'}
    except Exception as e:
        logger.error(f"Email connection test failed: {str(e)}")
        return {'success': False, 'message': f'Email connection failed: {str(e)}'}