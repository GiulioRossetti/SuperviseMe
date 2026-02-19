from superviseme.models import (
    User_mgmt,
    Supervisor_Role,
)

from flask import redirect, url_for, abort
from superviseme.utils.logging_config import log_privilege_escalation_attempt


def check_privileges(username, role="admin"):
    user = User_mgmt.query.filter_by(username=username).first()
    
    if not user:
        abort(404)

    # Handle the special case where a researcher might have supervisor privileges
    if role == "supervisor" and user.user_type == "researcher":
        # Check if the researcher has been granted supervisor role
        supervisor_role = Supervisor_Role.query.filter_by(
            researcher_id=user.id, active=True
        ).first()
        if supervisor_role:
            return True

    if user.user_type != role:
        # Log privilege escalation attempt
        log_privilege_escalation_attempt(username, f"Attempted to access {role} resources with {user.user_type} privileges")
        
        # Redirect to appropriate dashboard based on user type
        if user.user_type == "admin":
            return redirect(url_for("admin.dashboard"))
        elif user.user_type == "supervisor":
            return redirect(url_for("supervisor.dashboard"))
        elif user.user_type == "researcher":
            return redirect(url_for("researcher.dashboard"))
        elif user.user_type == "student":
            return redirect(url_for("student.dashboard"))
        else:
            abort(403)
    return True


def user_has_supervisor_role(user):
    """Check if a researcher user has been granted supervisor privileges"""
    if user.user_type == "supervisor":
        return True
    elif user.user_type == "researcher":
        supervisor_role = Supervisor_Role.query.filter_by(
            researcher_id=user.id, active=True
        ).first()
        return supervisor_role is not None
    return False
