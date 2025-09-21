from superviseme.models import (
    User_mgmt,
)

from flask import redirect, url_for, abort


def check_privileges(username, role="admin"):
    user = User_mgmt.query.filter_by(username=username).first()
    
    if not user:
        abort(404)

    if user.user_type != role:
        # Redirect to appropriate dashboard based on user type
        if user.user_type == "admin":
            return redirect(url_for("admin.dashboard"))
        elif user.user_type == "supervisor":
            return redirect(url_for("supervisor.dashboard"))
        elif user.user_type == "student":
            return redirect(url_for("student.dashboard"))
        else:
            abort(403)
    return True
