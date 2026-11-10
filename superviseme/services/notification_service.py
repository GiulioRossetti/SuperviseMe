"""
superviseme/services/notification_service.py
----------------------------------------------
Service layer wrapping the existing notification utilities.
Routes should call these functions instead of importing utils directly.

Bug fix (Stage 7): corrected all Notification field references from the
invalid `user_id` / `related_id` to the actual model columns:
  recipient_id, actor_id, thesis_id, title
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# System actor sentinel – used when no real actor is available (e.g. automated
# notifications from the scheduler).  Callers should supply a real actor_id
# whenever a human action triggered the notification.
_SYSTEM_ACTOR_ID: Optional[int] = None


def send_notification(
    recipient_id: int,
    message: str,
    notification_type: str = "general",
    thesis_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    title: Optional[str] = None,
    action_url: Optional[str] = None,
) -> bool:
    """Create a notification for *recipient_id* and optionally dispatch via Telegram.

    Returns True if the notification was persisted, False on error.

    Args:
        recipient_id:       ID of the user who should receive the notification.
        message:            Full notification body (may be markdown).
        notification_type:  Category tag, e.g. "new_update", "new_feedback".
        thesis_id:          Optional FK to the related Thesis row.
        actor_id:           ID of the user who triggered the notification.
                            Defaults to *recipient_id* when None (self-notification).
        title:              Short one-line summary shown in the notification badge.
                            Defaults to a truncated version of *message*.
        action_url:         Relative URL to navigate to when the notification is clicked.
    """
    try:
        from superviseme import db
        from superviseme.models import Notification
        from superviseme.utils.timestamps import to_int, utcnow

        resolved_actor_id = actor_id if actor_id is not None else recipient_id
        resolved_title = (title or message[:200]).strip() or "Notification"

        notif = Notification(
            recipient_id=recipient_id,
            actor_id=resolved_actor_id,
            thesis_id=thesis_id,
            notification_type=notification_type,
            title=resolved_title,
            message=message,
            action_url=action_url,
            created_at=to_int(utcnow()),
            is_read=False,
        )
        db.session.add(notif)
        db.session.commit()

        # Invalidate cached unread count for this user
        invalidate_unread_count(recipient_id)

        # Attempt Telegram dispatch (best-effort — failure must not crash caller)
        try:
            from superviseme.utils.telegram_service import get_telegram_service
            from superviseme.models import User_mgmt

            user = db.session.get(User_mgmt, recipient_id)
            if user and user.telegram_enabled and user.telegram_user_id:
                svc = get_telegram_service()
                svc.send_message(user.telegram_user_id, f"*{resolved_title}*\n{message}")
        except Exception as telegram_exc:
            logger.warning(
                "Telegram dispatch failed for user %s: %s", recipient_id, telegram_exc
            )

        return True

    except Exception as exc:
        logger.error("send_notification failed for user %s: %s", recipient_id, exc)
        return False


def get_unread_count(user_id: int) -> int:
    """Return the number of unread notifications for *user_id*.

    Result is cached for 30 seconds (CACHE_DEFAULT_TIMEOUT) to avoid
    hitting the database on every page load.
    """
    try:
        from superviseme import cache
        cache_key = f"notif_count_{user_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        from superviseme.models import Notification
        count = Notification.query.filter_by(recipient_id=user_id, is_read=False).count()
        cache.set(cache_key, count)
        return count
    except Exception as exc:
        logger.error("get_unread_count failed for user %s: %s", user_id, exc)
        return 0


def invalidate_unread_count(user_id: int) -> None:
    """Evict the cached unread count for *user_id* (call after mark_read / new notification)."""
    try:
        from superviseme import cache
        cache.delete(f"notif_count_{user_id}")
    except Exception as exc:
        logger.warning("invalidate_unread_count failed for user %s: %s", user_id, exc)


def mark_all_read(user_id: int) -> int:
    """Mark all notifications for *user_id* as read.  Returns count updated."""
    try:
        from superviseme import db
        from superviseme.models import Notification
        updated = (
            Notification.query.filter_by(recipient_id=user_id, is_read=False)
            .update({"is_read": True})
        )
        db.session.commit()
        invalidate_unread_count(user_id)
        return updated
    except Exception as exc:
        logger.error("mark_all_read failed for user %s: %s", user_id, exc)
        return 0
