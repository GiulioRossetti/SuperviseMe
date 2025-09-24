"""
Notification system utilities for SuperviseMe
Handles creating and managing notifications for user activities
"""

from superviseme.models import Notification, User_mgmt, Thesis
from superviseme import db
import time
import logging

logger = logging.getLogger(__name__)


def create_notification(recipient_id, actor_id, notification_type, title, message, 
                       thesis_id=None, action_url=None):
    """
    Create a new notification and send via enabled channels (in-app, Telegram)
    
    Args:
        recipient_id: User ID who will receive the notification
        actor_id: User ID who performed the action
        notification_type: Type of notification (e.g., "new_update", "new_feedback")
        title: Short notification title
        message: Detailed notification message
        thesis_id: Optional thesis ID if notification relates to a thesis
        action_url: Optional URL to relevant page
    """
    notification = Notification(
        recipient_id=recipient_id,
        actor_id=actor_id,
        notification_type=notification_type,
        title=title,
        message=message,
        thesis_id=thesis_id,
        action_url=action_url,
        created_at=int(time.time())
    )
    
    db.session.add(notification)
    db.session.commit()
    
    # Send Telegram notification if enabled for user
    try:
        from superviseme.utils.telegram_service import send_telegram_notification
        telegram_sent = send_telegram_notification(
            recipient_id, notification_type, title, message, action_url
        )
        
        if telegram_sent:
            notification.telegram_sent = True
            notification.telegram_sent_at = int(time.time())
            db.session.commit()
            
    except ImportError:
        logger.warning("Telegram service not available")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
    
    return notification


def create_thesis_update_notification(thesis_id, student_id, update_content):
    """
    Create notification when student posts an update
    """
    thesis = Thesis.query.get(thesis_id)
    if not thesis:
        return
    
    # Get all supervisors of this thesis
    from superviseme.models import Thesis_Supervisor
    supervisors = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).all()
    
    student = User_mgmt.query.get(student_id)
    student_name = f"{student.name} {student.surname}" if student else "A student"
    
    title = f"New update on {thesis.title}"
    message = f"{student_name} posted a new update: {update_content[:100]}..."
    action_url = f"/thesis/{thesis_id}"
    
    # Create notification for each supervisor
    for supervisor_rel in supervisors:
        create_notification(
            recipient_id=supervisor_rel.supervisor_id,
            actor_id=student_id,
            notification_type="new_update",
            title=title,
            message=message,
            thesis_id=thesis_id,
            action_url=action_url
        )


def create_supervisor_feedback_notification(thesis_id, supervisor_id, feedback_content):
    """
    Create notification when supervisor provides feedback
    """
    thesis = Thesis.query.get(thesis_id)
    if not thesis or not thesis.author_id:
        return
    
    supervisor = User_mgmt.query.get(supervisor_id)
    supervisor_name = f"{supervisor.name} {supervisor.surname}" if supervisor else "Your supervisor"
    
    title = f"New feedback on {thesis.title}"
    message = f"{supervisor_name} provided feedback: {feedback_content[:100]}..."
    action_url = f"/thesis"
    
    create_notification(
        recipient_id=thesis.author_id,
        actor_id=supervisor_id,
        notification_type="new_feedback",
        title=title,
        message=message,
        thesis_id=thesis_id,
        action_url=action_url
    )


def create_todo_assignment_notification(todo_id, assigner_id, assignee_id):
    """
    Create notification when a todo is assigned
    """
    from superviseme.models import Todo
    todo = Todo.query.get(todo_id)
    if not todo:
        return
    
    assigner = User_mgmt.query.get(assigner_id)
    assigner_name = f"{assigner.name} {assigner.surname}" if assigner else "Someone"
    
    title = f"New task assigned: {todo.title}"
    message = f"{assigner_name} assigned you a new task: {todo.description[:100]}..."
    action_url = f"/thesis#todos" if todo.thesis_id else "#"
    
    create_notification(
        recipient_id=assignee_id,
        actor_id=assigner_id,
        notification_type="todo_assigned",
        title=title,
        message=message,
        thesis_id=todo.thesis_id,
        action_url=action_url
    )


def create_thesis_status_change_notification(thesis_id, changer_id, new_status):
    """
    Create notification when thesis status changes
    """
    thesis = Thesis.query.get(thesis_id)
    if not thesis:
        return
    
    changer = User_mgmt.query.get(changer_id)
    changer_name = f"{changer.name} {changer.surname}" if changer else "System"
    
    title = f"Thesis status updated: {thesis.title}"
    message = f"{changer_name} changed the status to '{new_status}'"
    
    # Notify student
    if thesis.author_id:
        create_notification(
            recipient_id=thesis.author_id,
            actor_id=changer_id,
            notification_type="status_change",
            title=title,
            message=message,
            thesis_id=thesis_id,
            action_url="/thesis"
        )
    
    # Notify supervisors
    from superviseme.models import Thesis_Supervisor
    supervisors = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).all()
    
    for supervisor_rel in supervisors:
        if supervisor_rel.supervisor_id != changer_id:  # Don't notify the person who made the change
            create_notification(
                recipient_id=supervisor_rel.supervisor_id,
                actor_id=changer_id,
                notification_type="status_change",
                title=title,
                message=message,
                thesis_id=thesis_id,
                action_url=f"/thesis/{thesis_id}"
            )


def get_user_notifications(user_id, limit=10, unread_only=False):
    """
    Get notifications for a user
    
    Args:
        user_id: User ID to get notifications for
        limit: Maximum number of notifications to return
        unread_only: If True, only return unread notifications
    """
    query = Notification.query.filter_by(recipient_id=user_id)
    
    if unread_only:
        query = query.filter_by(is_read=False)
    
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


def mark_notification_as_read(notification_id):
    """
    Mark a notification as read
    """
    notification = Notification.query.get(notification_id)
    if notification:
        notification.is_read = True
        db.session.commit()


def mark_all_notifications_as_read(user_id):
    """
    Mark all notifications for a user as read
    """
    notifications = Notification.query.filter_by(recipient_id=user_id, is_read=False).all()
    for notification in notifications:
        notification.is_read = True
    db.session.commit()


def get_unread_notification_count(user_id):
    """
    Get count of unread notifications for a user
    """
    return Notification.query.filter_by(recipient_id=user_id, is_read=False).count()