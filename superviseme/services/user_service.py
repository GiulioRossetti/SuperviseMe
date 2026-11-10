"""
superviseme/services/user_service.py
--------------------------------------
Service layer for user-related business logic.
"""
from __future__ import annotations

import logging
from typing import Optional

from superviseme import db
from superviseme.models import User_mgmt

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20


def get_user_by_username(username: str) -> Optional[User_mgmt]:
    return User_mgmt.query.filter_by(username=username).first()


def get_user_by_email(email: str) -> Optional[User_mgmt]:
    return User_mgmt.query.filter_by(email=email).first()


def get_users_by_role(
    role: str,
    page: int = 1,
    per_page: int = DEFAULT_PAGE_SIZE,
    enabled_only: bool = True,
):
    """Return paginated users with *role*.

    Parameters
    ----------
    role:         one of admin / supervisor / student / researcher.
    page:         1-based page number.
    per_page:     items per page.
    enabled_only: when True, exclude disabled accounts.
    """
    query = User_mgmt.query.filter_by(user_type=role)
    if enabled_only:
        query = query.filter_by(is_enabled=True)
    return query.order_by(User_mgmt.id).paginate(
        page=page, per_page=per_page, error_out=False
    )


def get_all_users(
    page: int = 1,
    per_page: int = DEFAULT_PAGE_SIZE,
    search: str | None = None,
):
    """Return paginated users (admin view).  Optionally filter by name/username."""
    from sqlalchemy import or_
    query = User_mgmt.query
    if search:
        kw = f"%{search}%"
        query = query.filter(
            or_(
                User_mgmt.username.ilike(kw),
                User_mgmt.name.ilike(kw),
                User_mgmt.surname.ilike(kw),
                User_mgmt.email.ilike(kw),
            )
        )
    return query.order_by(User_mgmt.id).paginate(
        page=page, per_page=per_page, error_out=False
    )


def enable_user(user_id: int) -> bool:
    """Enable a user account.  Returns True on success."""
    user = db.session.get(User_mgmt, user_id)
    if user is None:
        return False
    user.is_enabled = True
    db.session.commit()
    logger.info("User %s (id=%s) enabled", user.username, user_id)
    return True


def disable_user(user_id: int) -> bool:
    """Disable a user account.  Returns True on success."""
    user = db.session.get(User_mgmt, user_id)
    if user is None:
        return False
    user.is_enabled = False
    db.session.commit()
    logger.info("User %s (id=%s) disabled", user.username, user_id)
    return True
