from superviseme.models import (
    User_mgmt,
)

from flask import redirect, url_for


def check_privileges(username, role="admin"):
    user = User_mgmt.query.filter_by(username=username).first()

    if user.user_type != role:
        return redirect(url_for(f"{user.user_type}.index"))
    return True
