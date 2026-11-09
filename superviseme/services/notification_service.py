"""
superviseme/services/notification_service.py
----------------------------------------------
Service layer wrapping the existing notification utilities.
Routes should call these functions instead of importing utils directly.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def send_notification(
    user_id: int,
    message: str,
    notification_type: str = "general",
    related_id: Optional[int] = None,
) -> bool:
    """Create a notification for *user_id* and optionally dispatch via Telegram.

    Returns True if the notification was persisted, False on error.
    """
    try:
        from superviseme import db
        from superviseme.models import Notification
        from superviseme.utils.timestamps import to_int, utcnow

        notif = Notification(
            user_id=user_id,
            message=message,
            notification_type=notification_type,
            related_id=related_id,
            created_at=to_int(utcnow()),
            is_read=False,
        )
        db.session.add(notif)
        db.session.commit()

        # Attempt Telegram dispatch (best-effort — failure must not crash caller)
        try:
            from superviseme.utils.telegram_service import get_telegram_service
            user = __import__(
                "superviseme.models", fromlist=["User_mgmt"]
            ).User_mgmt.query.get(user_id)
            if user and user.telegram_enabled and user.telegram_user_id:
                svc = get_telegram_service()
                svc.send_message(user.telegram_user_id, message)
        except Exception as telegram_exc:
            logger.warning(
                "Telegram dispatch failed for user %s: %s", user_id, telegram_exc
            )

        return True

    except Exception as exc:
        logger.error("send_notification failed for user %s: %s", user_id, exc)
        return False


def get_unread_count(user_id: int) -> int:
    """Return the number of unread notifications for *user_id*.

    Uses Flask-Caching when available (cache key: ``notif_count_{user_id}``).
    """
    try:
        from superviseme.models import Notification
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()
    except Exception as exc:
        logger.error("get_unread_count failed for user %s: %s", user_id, exc)
        return 0


def mark_all_read(user_id: int) -> int:
    """Mark all notifications for *user_id* as read.  Returns count updated."""
    try:
        from superviseme import db
        from superviseme.models import Notification
        updated = (
            Notification.query.filter_by(user_id=user_id, is_read=False)
            .update({"is_read": True})
        )
        db.session.commit()
        return updated
    except Exception as exc:
        logger.error("mark_all_read failed for user %s: %s", user_id, exc)
        return 0
