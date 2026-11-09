"""
superviseme/utils/decorators.py
--------------------------------
Route decorators for role-based access control.

Replace the fragile ``check_privileges(username, role=...)`` pattern:

    # Old pattern (returns True or redirect — callers must check)
    result = check_privileges(current_user.username, role="supervisor")
    if result is not True:
        return result

    # New pattern (raises 403 or redirects immediately — cleaner)
    @supervisor.route("/supervisor/some-view")
    @login_required
    @requires_role("supervisor")
    def some_view():
        ...

Multiple allowed roles can be specified:

    @requires_role("supervisor", "researcher")

"""
from __future__ import annotations

import functools
import logging

from flask import abort, flash, redirect, url_for
from flask_login import current_user

logger = logging.getLogger(__name__)

# Maps each role to its dashboard endpoint (used for redirect-on-wrong-role)
_ROLE_DASHBOARD: dict[str, str] = {
    "admin": "admin.dashboard",
    "supervisor": "supervisor.dashboard",
    "student": "student.dashboard",
    "researcher": "researcher.dashboard",
}


def requires_role(*roles: str):
    """Decorator that restricts a view to users with one of the given roles.

    Behaviour:
    - Unauthenticated users are handled by ``@login_required`` (should be
      applied before this decorator).
    - Disabled accounts receive HTTP 403.
    - Wrong role: flash a message and redirect to the user's own dashboard.
    - Matching role: proceed normally.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                # Shouldn't happen when @login_required is used, but be safe.
                return redirect(url_for("auth.login"))

            if not current_user.is_enabled:
                abort(403)

            if current_user.user_type not in roles:
                logger.warning(
                    "Access denied: user %s (role=%s) tried to access %s (requires %s)",
                    current_user.username,
                    current_user.user_type,
                    f.__name__,
                    roles,
                )
                flash("You do not have permission to access that page.", "warning")
                dashboard = _ROLE_DASHBOARD.get(current_user.user_type, "auth.login")
                return redirect(url_for(dashboard))

            return f(*args, **kwargs)

        return wrapped
    return decorator
