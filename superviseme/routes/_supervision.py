"""Helpers shared by the supervision views that serve both blueprints.

Supervisors use ``/supervisor/...``; researchers granted the supervisor role use the very same
view functions under ``/researcher/supervisor/...`` (registered at the bottom of
``researcher.py``). The view decides which side it is serving from ``request.blueprint``.
"""
from flask import flash, redirect, request, url_for
from flask_login import current_user

from superviseme.utils.miscellanea import check_privileges, user_has_supervisor_role

_ENDPOINTS = {
    # logical name: (supervisor endpoint, researcher endpoint)
    "dashboard": ("supervisor.dashboard", "researcher.dashboard"),
    "thesis_detail": ("supervisor.thesis_detail", "researcher.supervisor_thesis_detail"),
    "theses": ("supervisor.theses_data", "researcher.supervisor_theses"),
}


def acting_as_researcher():
    return request.blueprint == "researcher"


def ep(name):
    """Endpoint to redirect to for the side (supervisor / researcher) serving this request."""
    return _ENDPOINTS[name][1 if acting_as_researcher() else 0]


def supervision_gate():
    """Return True when the current user may supervise, otherwise a response to return."""
    if acting_as_researcher():
        check = check_privileges(current_user.username, role="researcher")
        if check is not True:
            return check
        if not user_has_supervisor_role(current_user):
            flash("You don't have supervisor privileges")
            return redirect(url_for("researcher.dashboard"))
        return True
    return check_privileges(current_user.username, role="supervisor")
