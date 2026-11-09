"""Workflow features: milestones (and, in later commits, meetings, documents, checklist, ...)."""
import time

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from superviseme import db
from superviseme.models import Thesis_Milestone, Thesis_Reviewer, Thesis_Supervisor, User_mgmt
from superviseme.utils.workflow import READ_ROLES, can_manage_team, load_thesis_or_403, parse_date, safe_next, thesis_role

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


# ═══════════════════════════ Documents: versions and comments ═══════════════════════════
import os  # noqa: E402

from flask import send_file  # noqa: E402

from superviseme.models import Document_Comment, Thesis_Document, Thesis_Document_Version  # noqa: E402
from superviseme.utils import documents as doc_utils  # noqa: E402
from superviseme.utils.uploads import UploadError, delete_file, resolve_path  # noqa: E402


def _participants(thesis, exclude=None):
    ids = {ts.supervisor_id for ts in Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all()}
    ids |= {r.reviewer_id for r in Thesis_Reviewer.query.filter_by(thesis_id=thesis.id).all()}
    if thesis.author_id:
        ids.add(thesis.author_id)
    ids.discard(exclude)
    return ids


def _notify_many(ids, actor_id, title, message, thesis_id):
    from superviseme.utils.notifications import create_notification
    for uid in ids:
        create_notification(uid, actor_id, "new_update", title, message, thesis_id=thesis_id)


def _store_version(doc, file, note):
    stored, original, size = doc_utils.save_pdf(file)
    number = (doc.versions[0].version + 1) if doc.versions else 1
    v = Thesis_Document_Version(document=doc, version=number, filename=stored, original_name=original, size=size,
                                note=(note or "").strip()[:500] or None, uploaded_by=current_user.id, created_at=int(time.time()))
    db.session.add(v)
    return v


@workflow.route("/thesis/<int:thesis_id>/documents/add", methods=["POST"])
@login_required
def add_document(thesis_id):
    thesis, _role = load_thesis_or_403(current_user, thesis_id)
    title = (request.form.get("title") or "").strip()[:200]
    if not title:
        flash(_("Please give the document a title."), "error")
        return redirect(safe_next(fallback=thesis_url(current_user, thesis)))
    if len(thesis.documents) >= doc_utils.MAX_DOCUMENTS:
        flash(_("Too many documents for this thesis."), "error")
        return redirect(safe_next(fallback=thesis_url(current_user, thesis)))
    doc = Thesis_Document(thesis_id=thesis.id, title=title, created_by=current_user.id, created_at=int(time.time()))
    db.session.add(doc)
    try:
        _store_version(doc, request.files.get("file"), request.form.get("note"))
    except UploadError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(safe_next(fallback=thesis_url(current_user, thesis)))
    db.session.commit()
    _notify_many(_participants(thesis, current_user.id), current_user.id, _("New document: %(t)s", t=title),
                 _("%(n)s uploaded a document.", n=current_user.name), thesis.id)
    flash(_("Document uploaded."), "success")
    return redirect(url_for("workflow.document_detail", doc_id=doc.id))


def _doc_for(doc_id, roles=("admin", "supervisor", "student")):
    doc = Thesis_Document.query.get_or_404(doc_id)
    thesis, role = load_thesis_or_403(current_user, doc.thesis_id, roles=roles)
    return doc, thesis, role


@workflow.route("/documents/<int:doc_id>/versions/add", methods=["POST"])
@login_required
def add_document_version(doc_id):
    doc, thesis, _role = _doc_for(doc_id)
    if len(doc.versions) >= doc_utils.MAX_VERSIONS:
        flash(_("This document reached the maximum number of versions."), "error")
        return redirect(url_for("workflow.document_detail", doc_id=doc.id))
    try:
        v = _store_version(doc, request.files.get("file"), request.form.get("note"))
    except UploadError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("workflow.document_detail", doc_id=doc.id))
    db.session.commit()
    _notify_many(_participants(thesis, current_user.id), current_user.id, _("New version of %(t)s", t=doc.title),
                 _("Version %(v)d was uploaded.", v=v.version), thesis.id)
    flash(_("Version uploaded."), "success")
    return redirect(url_for("workflow.document_detail", doc_id=doc.id, v=v.id))


@workflow.route("/documents/<int:doc_id>")
@login_required
def document_detail(doc_id):
    doc, thesis, role = _doc_for(doc_id, roles=READ_ROLES)
    selected = next((v for v in doc.versions if v.id == request.args.get("v", type=int)), doc.latest)
    previous = None
    if selected:
        older = [v for v in doc.versions if v.version < selected.version]
        previous = older[0] if older else None
    diff = None
    if selected and previous:
        a, b = resolve_path(previous.filename), resolve_path(selected.filename)
        if a and b:
            diff = doc_utils.compare_versions(a, b)
    return render_template("workflow/document.html", doc=doc, thesis=thesis, role=role, selected=selected, previous=previous,
                           diff=diff, dt=datetime.fromtimestamp, thesis_url=thesis_url)


@workflow.route("/documents/versions/<int:version_id>/file")
@login_required
def document_file(version_id):
    v = Thesis_Document_Version.query.get_or_404(version_id)
    load_thesis_or_403(current_user, v.document.thesis_id, roles=READ_ROLES)
    path = resolve_path(v.filename)
    if not path:
        abort(404)
    download = request.args.get("download") == "1"
    resp = send_file(path, mimetype="application/pdf", as_attachment=download,
                     download_name=f"{os.path.splitext(v.original_name)[0]}-v{v.version}.pdf", conditional=True)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "private, max-age=0"
    return resp


@workflow.route("/documents/versions/<int:version_id>/comments/add", methods=["POST"])
@login_required
def add_document_comment(version_id):
    v = Thesis_Document_Version.query.get_or_404(version_id)
    thesis, _role = load_thesis_or_403(current_user, v.document.thesis_id, roles=READ_ROLES)
    body = (request.form.get("body") or "").strip()[:3000]
    if not body:
        flash(_("The comment cannot be empty."), "error")
    else:
        db.session.add(Document_Comment(version_id=v.id, author_id=current_user.id, body=body,
                                        section=(request.form.get("section") or "").strip()[:100] or None,
                                        created_at=int(time.time())))
        db.session.commit()
        _notify_many(_participants(thesis, current_user.id), current_user.id, _("New comment on %(t)s", t=v.document.title),
                     body[:200], thesis.id)
    return redirect(url_for("workflow.document_detail", doc_id=v.document_id, v=v.id) + "#comments")


@workflow.route("/comments/<int:comment_id>/resolve", methods=["POST"])
@login_required
def resolve_document_comment(comment_id):
    c = Document_Comment.query.get_or_404(comment_id)
    load_thesis_or_403(current_user, c.version.document.thesis_id, roles=READ_ROLES)
    c.resolved = not c.resolved
    db.session.commit()
    return redirect(url_for("workflow.document_detail", doc_id=c.version.document_id, v=c.version_id) + "#comments")


@workflow.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    doc, thesis, role = _doc_for(doc_id)
    if role not in ("admin", "supervisor") and doc.created_by != current_user.id:
        abort(403)
    files = [v.filename for v in doc.versions]
    db.session.delete(doc)
    db.session.commit()
    for f in files:
        delete_file(f)
    flash(_("Document deleted."), "success")
    return redirect(thesis_url(current_user, thesis))


# ---------------------------------------------------------------- team (co-supervisors, reviewers)
def _team_back(thesis):
    return redirect(safe_next(fallback=thesis_url(current_user, thesis)))


@workflow.route("/thesis/<int:thesis_id>/team/add", methods=["POST"])
@login_required
def add_team_member(thesis_id):
    thesis, _role = load_thesis_or_403(current_user, thesis_id, roles=("admin", "supervisor"))
    if not can_manage_team(current_user, thesis):
        abort(403)
    kind = request.form.get("kind")
    user = User_mgmt.query.get(request.form.get("user_id", type=int) or 0)
    if kind not in ("co_supervisor", "reviewer") or not user or user.user_type not in ("supervisor", "researcher"):
        flash(_("Invalid selection."), "error")
        return _team_back(thesis)
    if thesis.author_id == user.id or Thesis_Supervisor.query.filter_by(thesis_id=thesis.id, supervisor_id=user.id).first() \
            or Thesis_Reviewer.query.filter_by(thesis_id=thesis.id, reviewer_id=user.id).first():
        flash(_("This person is already part of the team."), "warning")
        return _team_back(thesis)
    if kind == "co_supervisor":
        db.session.add(Thesis_Supervisor(thesis_id=thesis.id, supervisor_id=user.id, assigned_at=int(time.time()), role="co_supervisor"))
        label = _("co-supervisor")
    else:
        db.session.add(Thesis_Reviewer(thesis_id=thesis.id, reviewer_id=user.id, assigned_by=current_user.id, assigned_at=int(time.time())))
        label = _("reviewer")
    db.session.commit()
    _notify_many({user.id}, current_user.id, _("You were added as %(r)s", r=label), thesis.title, thesis.id)
    flash(_("Team updated."), "success")
    return _team_back(thesis)


@workflow.route("/thesis/<int:thesis_id>/team/remove", methods=["POST"])
@login_required
def remove_team_member(thesis_id):
    thesis, _role = load_thesis_or_403(current_user, thesis_id, roles=("admin", "supervisor"))
    if not can_manage_team(current_user, thesis):
        abort(403)
    uid = request.form.get("user_id", type=int) or 0
    # only co-supervisors and reviewers can be removed here; primary supervisors are managed elsewhere
    Thesis_Supervisor.query.filter_by(thesis_id=thesis.id, supervisor_id=uid, role="co_supervisor").delete()
    Thesis_Reviewer.query.filter_by(thesis_id=thesis.id, reviewer_id=uid).delete()
    db.session.commit()
    flash(_("Team updated."), "success")
    return _team_back(thesis)


@workflow.route("/reviews")
@login_required
def reviews():
    rows = Thesis_Reviewer.query.filter_by(reviewer_id=current_user.id).all()
    return render_template("workflow/reviews.html", rows=rows, dt=datetime.fromtimestamp)


@workflow.route("/reviews/<int:thesis_id>")
@login_required
def review_thesis(thesis_id):
    thesis, _role = load_thesis_or_403(current_user, thesis_id, roles=("reviewer",))
    supervisors = Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all()
    student = User_mgmt.query.get(thesis.author_id) if thesis.author_id else None
    return render_template("workflow/review_thesis.html", thesis=thesis, supervisors=supervisors, student=student,
                           mm_next=url_for("workflow.review_thesis", thesis_id=thesis.id), dt=datetime.fromtimestamp)
