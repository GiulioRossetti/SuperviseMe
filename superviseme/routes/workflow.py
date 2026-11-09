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


# ═══════════════════════════ Agenda: slots, meetings, calendar files ═══════════════════════════
from datetime import datetime, timedelta  # noqa: E402

from flask import Response, render_template  # noqa: E402

from superviseme.models import Availability_Slot, MeetingNote, Meeting, Thesis, Thesis_Supervisor, User_mgmt  # noqa: E402
from superviseme.utils import meetings as meeting_utils  # noqa: E402
from superviseme.utils.ics import build_calendar  # noqa: E402
from superviseme.utils.miscellanea import user_has_supervisor_role  # noqa: E402
from superviseme.utils.workflow import parse_local_datetime, thesis_url  # noqa: E402


def _is_supervisor():
    return current_user.user_type != "student" and user_has_supervisor_role(current_user)


def _agenda_back():
    return redirect(safe_next("workflow.agenda"))


@workflow.route("/agenda")
@login_required
def agenda():
    now = int(time.time())
    is_sup = _is_supervisor()
    ctx = {"is_sup": is_sup, "dt": datetime.fromtimestamp, "thesis_url": thesis_url}
    ctx["upcoming"] = meeting_utils.meetings_for(current_user, upcoming=True)
    ctx["past"] = meeting_utils.meetings_for(current_user, upcoming=False, limit=10)
    if is_sup:
        ctx["slots"] = (Availability_Slot.query.filter(Availability_Slot.supervisor_id == current_user.id, Availability_Slot.end_ts >= now)
                        .order_by(Availability_Slot.start_ts.asc()).limit(60).all())
        rows = (Thesis.query.join(Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id)
                .filter(Thesis_Supervisor.supervisor_id == current_user.id, Thesis.author_id.isnot(None),
                        Thesis.frozen.isnot(True)).all())
        ctx["schedulable"] = rows
    if current_user.user_type == "student":
        sup_ids = meeting_utils.supervisors_of_student(current_user.id)
        ctx["bookable"] = (Availability_Slot.query.filter(Availability_Slot.supervisor_id.in_(sup_ids), Availability_Slot.booked_by.is_(None),
                                                          Availability_Slot.start_ts > now)
                           .order_by(Availability_Slot.start_ts.asc()).limit(40).all()) if sup_ids else []
        ctx["has_thesis"] = bool(sup_ids)
    return render_template("workflow/agenda.html", **ctx)


@workflow.route("/agenda/slots/add", methods=["POST"])
@login_required
def add_slots():
    if not _is_supervisor():
        abort(403)
    start = parse_local_datetime(request.form.get("date"), request.form.get("time"))
    try:
        minutes = max(10, min(240, int(request.form.get("duration") or 30)))
        repeat = max(1, min(12, int(request.form.get("repeat") or 1)))
        count = max(1, min(8, int(request.form.get("count") or 1)))  # back-to-back slots in a row
    except ValueError:
        start = None
    if start is None or start < time.time():
        flash(_("Choose a valid date and time in the future."), "error")
        return _agenda_back()
    location = (request.form.get("location") or "").strip()[:200] or None
    added = 0
    for w in range(repeat):
        for i in range(count):
            s = start + w * 7 * 86400 + i * minutes * 60
            exists = Availability_Slot.query.filter_by(supervisor_id=current_user.id, start_ts=s).first()
            if not exists:
                db.session.add(Availability_Slot(supervisor_id=current_user.id, start_ts=s, end_ts=s + minutes * 60,
                                                 location=location, created_at=int(time.time())))
                added += 1
    db.session.commit()
    flash(_("%(n)d slots published.", n=added), "success")
    return _agenda_back()


@workflow.route("/agenda/slots/<int:slot_id>/delete", methods=["POST"])
@login_required
def delete_slot(slot_id):
    slot = Availability_Slot.query.get_or_404(slot_id)
    if slot.supervisor_id != current_user.id:
        abort(403)
    if slot.booked_by:
        flash(_("This slot is booked: cancel the meeting instead."), "error")
    else:
        db.session.delete(slot)
        db.session.commit()
    return _agenda_back()


@workflow.route("/agenda/slots/<int:slot_id>/book", methods=["POST"])
@login_required
def book_slot(slot_id):
    if current_user.user_type != "student":
        abort(403)
    slot = Availability_Slot.query.get_or_404(slot_id)
    thesis = (Thesis.query.join(Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id)
              .filter(Thesis.author_id == current_user.id, Thesis_Supervisor.supervisor_id == slot.supervisor_id).first())
    if not thesis:
        abort(403)
    meeting = meeting_utils.book_slot(slot_id, current_user, thesis)
    if not meeting:
        flash(_("Sorry, this slot is no longer available."), "error")
        return _agenda_back()
    from superviseme.utils.notifications import create_notification
    when = datetime.fromtimestamp(meeting.start_ts).strftime("%d %b %Y, %H:%M")
    create_notification(slot.supervisor_id, current_user.id, "deadline_reminder", _("New meeting booked"),
                        _("%(s)s booked a meeting on %(w)s.", s=current_user.name, w=when), thesis_id=thesis.id)
    flash(_("Meeting booked."), "success")
    return _agenda_back()


@workflow.route("/agenda/meetings/add", methods=["POST"])
@login_required
def add_meeting():
    if not _is_supervisor():
        abort(403)
    thesis = Thesis.query.get_or_404(request.form.get("thesis_id", type=int) or 0)
    if not Thesis_Supervisor.query.filter_by(thesis_id=thesis.id, supervisor_id=current_user.id).first() or not thesis.author_id:
        abort(403)
    start = parse_local_datetime(request.form.get("date"), request.form.get("time"))
    try:
        minutes = max(10, min(480, int(request.form.get("duration") or 30)))
    except ValueError:
        start = None
    if start is None:
        flash(_("Choose a valid date and time."), "error")
        return _agenda_back()
    title = (request.form.get("title") or "").strip()[:200] or f"Meeting: {thesis.title}"[:200]
    m = Meeting(thesis_id=thesis.id, supervisor_id=current_user.id, student_id=thesis.author_id, title=title, start_ts=start,
                end_ts=start + minutes * 60, location=(request.form.get("location") or "").strip()[:200] or None,
                created_by=current_user.id, created_at=int(time.time()))
    db.session.add(m)
    db.session.commit()
    from superviseme.utils.notifications import create_notification
    create_notification(thesis.author_id, current_user.id, "deadline_reminder", _("Meeting scheduled: %(t)s", t=title),
                        datetime.fromtimestamp(start).strftime("%d %b %Y, %H:%M"), thesis_id=thesis.id)
    flash(_("Meeting scheduled."), "success")
    return _agenda_back()


def _participant_meeting(meeting_id):
    m = Meeting.query.get_or_404(meeting_id)
    if current_user.user_type != "admin" and current_user.id not in (m.supervisor_id, m.student_id):
        abort(403)
    return m


@workflow.route("/agenda/meetings/<int:meeting_id>/cancel", methods=["POST"])
@login_required
def cancel_meeting(meeting_id):
    m = _participant_meeting(meeting_id)
    meeting_utils.cancel_meeting(m)
    other = m.student_id if current_user.id == m.supervisor_id else m.supervisor_id
    if other:
        from superviseme.utils.notifications import create_notification
        create_notification(other, current_user.id, "deadline_reminder", _("Meeting cancelled: %(t)s", t=m.title),
                            datetime.fromtimestamp(m.start_ts).strftime("%d %b %Y, %H:%M"), thesis_id=m.thesis_id)
    flash(_("Meeting cancelled."), "success")
    return _agenda_back()


def _ics_response(rows, filename, name):
    body = build_calendar(rows, name=name)
    return Response(body, mimetype="text/calendar", headers={
        "Content-Disposition": f'attachment; filename="{filename}"', "X-Content-Type-Options": "nosniff"})


def _meeting_dict(m):
    other = m.student if current_user.id == m.supervisor_id else m.supervisor
    return {"uid": m.id, "title": m.title, "start": m.start_ts, "end": m.end_ts, "location": m.location,
            "description": f"With {other.name} {other.surname}" if other else ""}


@workflow.route("/agenda/meetings/<int:meeting_id>.ics")
@login_required
def meeting_ics(meeting_id):
    m = _participant_meeting(meeting_id)
    return _ics_response([_meeting_dict(m)], f"meeting-{m.id}.ics", m.title)


@workflow.route("/agenda/calendar.ics")
@login_required
def calendar_ics():
    rows = [_meeting_dict(m) for m in meeting_utils.meetings_for(current_user, upcoming=True, limit=200)]
    return _ics_response(rows, "superviseme-agenda.ics", "SuperviseMe meetings")


# ═══════════════════════════ Meeting notes → tasks ═══════════════════════════
@workflow.route("/meeting-notes/<int:note_id>/action-items", methods=["POST"])
@login_required
def note_action_items(note_id):
    from superviseme.utils.action_items import create_todos_from_note
    note = MeetingNote.query.get_or_404(note_id)
    load_thesis_or_403(current_user, note.thesis_id)
    created, skipped = create_todos_from_note(note, current_user)
    if created:
        flash(_("%(n)d tasks created from the meeting note.", n=created), "success")
    else:
        flash(_("No new action items found (use lines like “- [ ] Task @due:2026-12-01 @student”)."), "info")
    return redirect(safe_next("workflow.agenda"))
