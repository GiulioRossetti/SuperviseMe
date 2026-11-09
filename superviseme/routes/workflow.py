"""Workflow features: milestones (and, in later commits, meetings, documents, checklist, ...)."""
import time

from flask import Blueprint, abort, flash, redirect, request
from flask_babel import gettext as _
from flask_login import current_user, login_required

from superviseme import db
from superviseme.models import Thesis_Milestone
from superviseme.utils.workflow import load_thesis_or_403, parse_date, safe_next, thesis_role

workflow = Blueprint("workflow", __name__)


def _back(thesis_id):
    return redirect(safe_next("public.public_thesis_dashboard"))


@workflow.route("/thesis/<int:thesis_id>/milestones/add", methods=["POST"])
@login_required
def add_milestone(thesis_id):
    thesis, _role = load_thesis_or_403(current_user, thesis_id, roles=("admin", "supervisor"))
    title = (request.form.get("title") or "").strip()[:200]
    due = parse_date(request.form.get("due_date"))
    if not title or due is None:
        flash(_("A title and a valid due date are required."), "error")
        return _back(thesis_id)
    if len(thesis.milestones) >= 50:
        flash(_("Too many milestones for this thesis."), "error")
        return _back(thesis_id)
    desc = (request.form.get("description") or "").strip()[:1000] or None
    db.session.add(Thesis_Milestone(thesis_id=thesis.id, title=title, description=desc, due_date=due,
                                    created_by=current_user.id, created_at=int(time.time())))
    db.session.commit()
    if thesis.author_id:
        from superviseme.utils.notifications import create_notification
        create_notification(thesis.author_id, current_user.id, "thesis_status_change", _("New milestone: %(t)s", t=title),
                            _("A new milestone was added to your thesis roadmap."), thesis_id=thesis.id)
    flash(_("Milestone added."), "success")
    return _back(thesis_id)


def _milestone_for(milestone_id, roles):
    m = Thesis_Milestone.query.get_or_404(milestone_id)
    thesis, role = load_thesis_or_403(current_user, m.thesis_id, roles=roles)
    return m, thesis


@workflow.route("/milestones/<int:milestone_id>/toggle", methods=["POST"])
@login_required
def toggle_milestone(milestone_id):
    m, thesis = _milestone_for(milestone_id, ("admin", "supervisor", "student"))
    if m.status == "done":
        m.status, m.completed_at = "pending", None
    else:
        m.status, m.completed_at = "done", int(time.time())
    db.session.commit()
    return _back(thesis.id)


@workflow.route("/milestones/<int:milestone_id>/delete", methods=["POST"])
@login_required
def delete_milestone(milestone_id):
    m, thesis = _milestone_for(milestone_id, ("admin", "supervisor"))
    db.session.delete(m)
    db.session.commit()
    flash(_("Milestone removed."), "success")
    return _back(thesis.id)
