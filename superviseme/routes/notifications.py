from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from superviseme.utils.notifications import (
    get_user_notifications, 
    mark_notification_as_read, 
    mark_all_notifications_as_read,
    get_unread_notification_count
)
from datetime import datetime

notifications = Blueprint("notifications", __name__)


@notifications.route("/notifications")
@login_required
def notifications_page():
    """
    Render the notifications page
    """
    # Get all notifications for the current user
    user_notifications = get_user_notifications(
        user_id=current_user.id,
        limit=100,  # Get more notifications for the full page
        unread_only=False
    )
    
    unread_count = get_unread_notification_count(current_user.id)
    
    return render_template("notifications.html", 
                         notifications=user_notifications, 
                         unread_count=unread_count,
                         dt=datetime.fromtimestamp)


@notifications.route("/api/notifications")
@login_required
def get_notifications():
    """
    Get notifications for the current user
    """
    limit = request.args.get('limit', 10, type=int)
    unread_only = request.args.get('unread_only', False, type=bool)
    
    user_notifications = get_user_notifications(
        user_id=current_user.id,
        limit=limit,
        unread_only=unread_only
    )
    
    notifications_data = []
    for notification in user_notifications:
        notifications_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'is_read': notification.is_read,
            'created_at': notification.created_at,
            'action_url': notification.action_url,
            'actor': {
                'name': notification.actor.name,
                'surname': notification.actor.surname
            } if notification.actor else None,
            'thesis_title': notification.thesis.title if notification.thesis else None
        })
    
    return jsonify({
        'notifications': notifications_data,
        'unread_count': get_unread_notification_count(current_user.id)
    })


@notifications.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    """
    Mark a specific notification as read
    """
    mark_notification_as_read(notification_id)
    return jsonify({'success': True})


@notifications.route("/api/notifications/mark_all_read", methods=["POST"])
@login_required
def mark_all_read():
    """
    Mark all notifications as read for current user
    """
    mark_all_notifications_as_read(current_user.id)
    return jsonify({'success': True})


@notifications.route("/api/notifications/unread_count")
@login_required
def get_unread_count():
    """
    Get count of unread notifications
    """
    count = get_unread_notification_count(current_user.id)
    return jsonify({'unread_count': count})


@notifications.route("/api/notifications/<int:notification_id>/delete", methods=["DELETE"])
@login_required
def delete_notification(notification_id):
    """
    Delete a specific notification
    """
    from superviseme.models import Notification
    from superviseme import db
    
    notification = Notification.query.filter_by(
        id=notification_id, 
        recipient_id=current_user.id
    ).first()
    
    if notification:
        db.session.delete(notification)
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Notification not found'}), 404


@notifications.route("/api/notifications/clear_all", methods=["DELETE"])
@login_required
def clear_all_notifications():
    """
    Clear all notifications for current user
    """
    from superviseme.models import Notification
    from superviseme import db
    
    notifications = Notification.query.filter_by(recipient_id=current_user.id).all()
    for notification in notifications:
        db.session.delete(notification)
    
    db.session.commit()
    return jsonify({'success': True})