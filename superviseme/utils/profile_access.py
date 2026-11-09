"""Who may open whose read-only profile page, and the ``user_link`` template helper."""
from flask import request, url_for
from markupsafe import Markup, escape

from superviseme import db
from superviseme.models import Thesis, Thesis_Supervisor


def can_view_profile(viewer, target):
    if viewer is None or not getattr(viewer, "is_authenticated", False) or target is None:
        return False
    if viewer.id == target.id or viewer.user_type == "admin":
        return True
    if target.user_type != "student":
        return True  # staff profiles are visible to every signed-in user
    # student profiles: only the people supervising one of their theses
    return db.session.query(Thesis_Supervisor.id).join(Thesis, Thesis.id == Thesis_Supervisor.thesis_id).filter(
        Thesis.author_id == target.id, Thesis_Supervisor.supervisor_id == viewer.id).first() is not None


def user_link(user, css_class="user-link"):
    """Render a user's full name, linked to their read-only profile when the viewer may open it."""
    from flask_login import current_user
    if not user:
        return ""
    name = escape(("%s %s" % (user.name or "", user.surname or "")).strip() or user.username)
    if not getattr(current_user, "is_authenticated", False):
        # anonymous visitors of the public catalog: staff names still link to the profile,
        # which asks them to sign in first (login_required keeps the destination).
        if user.user_type == "student":
            return Markup(name)
        return Markup('<a class="%s" href="%s">%s</a>') % (css_class, url_for("public.user_profile", user_id=user.id), name)
    cache = request._get_current_object().__dict__.setdefault("_profile_access_cache", {})
    if user.id not in cache:
        cache[user.id] = can_view_profile(current_user, user)
    if not cache[user.id]:
        return Markup(name)
    return Markup('<a class="%s" href="%s">%s</a>') % (css_class, url_for("public.user_profile", user_id=user.id), name)
