"""
Activity tracking utilities for SuperviseMe application
"""
from flask_login import current_user
from superviseme import db
import time
import logging

logger = logging.getLogger(__name__)


def update_user_activity(location="platform"):
    """
    Update the current user's last activity timestamp and location
    
    Args:
        location (str): Description of where the user was active (e.g., "thesis_detail", "post_update")
    """
    if current_user.is_authenticated:
        try:
            current_user.last_activity = int(time.time())
            current_user.last_activity_location = location
            db.session.commit()
            logger.debug(f"Updated activity for user {current_user.username} at {location}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update activity for user {current_user.username}: {str(e)}")


def get_inactive_students(supervisor_id, weeks_threshold=2):
    """
    Get students supervised by the given supervisor who have been inactive for more than the threshold
    
    Args:
        supervisor_id (int): ID of the supervisor
        weeks_threshold (int): Number of weeks to consider as inactive threshold
    
    Returns:
        list: List of student data with inactivity information
    """
    from superviseme.models import User_mgmt, Thesis_Supervisor, Thesis
    
    cutoff_time = int(time.time()) - (weeks_threshold * 7 * 24 * 60 * 60)  # Convert weeks to seconds
    
    # Query students through thesis supervision relationships
    inactive_students = []
    
    # Get all thesis supervisors for this supervisor
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=supervisor_id).all()
    
    for ts in thesis_supervisors:
        if ts.thesis and ts.thesis.author and ts.thesis.author.user_type == 'student':
            student = ts.thesis.author
            
            # Check if student is inactive (no activity recorded or activity older than threshold)
            is_inactive = (
                student.last_activity is None or 
                student.last_activity < cutoff_time
            )
            
            inactive_students.append({
                'student': student,
                'thesis': ts.thesis,
                'is_inactive': is_inactive,
                'days_inactive': None if student.last_activity is None else 
                                (int(time.time()) - student.last_activity) // (24 * 60 * 60),
                'last_activity_location': student.last_activity_location
            })
    
    return inactive_students


def get_weekly_activity_summary(supervisor_id):
    """
    Get a weekly activity summary for all students supervised by the given supervisor
    
    Args:
        supervisor_id (int): ID of the supervisor
    
    Returns:
        dict: Weekly activity summary data
    """
    from superviseme.models import User_mgmt, Thesis_Supervisor, Thesis, Thesis_Update
    
    # Get time range for the past week
    one_week_ago = int(time.time()) - (7 * 24 * 60 * 60)
    
    students_activity = []
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=supervisor_id).all()
    
    for ts in thesis_supervisors:
        if ts.thesis and ts.thesis.author and ts.thesis.author.user_type == 'student':
            student = ts.thesis.author
            thesis = ts.thesis
            
            # Get updates from this week
            recent_updates = Thesis_Update.query.filter(
                Thesis_Update.thesis_id == thesis.id,
                Thesis_Update.author_id == student.id,
                Thesis_Update.created_at >= one_week_ago
            ).count()
            
            # Check activity status
            is_inactive = (
                student.last_activity is None or 
                student.last_activity < (int(time.time()) - (14 * 24 * 60 * 60))  # 2 weeks
            )
            
            students_activity.append({
                'student': student,
                'thesis': thesis,
                'recent_updates': recent_updates,
                'is_inactive': is_inactive,
                'last_activity_location': student.last_activity_location,
                'days_since_activity': None if student.last_activity is None else 
                                     (int(time.time()) - student.last_activity) // (24 * 60 * 60)
            })
    
    return {
        'students': students_activity,
        'total_students': len(students_activity),
        'active_students': sum(1 for s in students_activity if not s['is_inactive']),
        'inactive_students': sum(1 for s in students_activity if s['is_inactive']),
        'total_updates_this_week': sum(s['recent_updates'] for s in students_activity)
    }