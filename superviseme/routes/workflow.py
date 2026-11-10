"""Workflow features: milestones (and, in later commits, meetings, documents, checklist, ...)."""
import time

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
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
from datetime import date, datetime, timedelta  # noqa: E402

from flask import Response, render_template  # noqa: E402

from superviseme.models import Availability_Slot, MeetingNote, Meeting, Thesis, Thesis_Supervisor, User_mgmt  # noqa: E402
from superviseme.utils import meetings as meeting_utils  # noqa: E402
from superviseme.utils.ics import build_calendar  # noqa: E402
from superviseme.utils.miscellanea import user_has_supervisor_role  # noqa: E402
from superviseme.utils.workflow import clean_call_url, parse_local_datetime, thesis_url  # noqa: E402


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
        from superviseme.utils import calendar_feed as cf
        ctx["feed"] = cf.status(current_user.id)
        last_end = max([sl.end_ts for sl in ctx["slots"]] + [now])
        busy = cf.busy_for(current_user.id, now, last_end) if ctx["feed"] else []
        ctx["conflicting"] = {sl.id for sl in ctx["slots"] if not sl.booked_by and any(b[0] < sl.end_ts and b[1] > sl.start_ts for b in busy)}
    if current_user.user_type == "student":
        sup_ids = meeting_utils.supervisors_of_student(current_user.id)
        ctx["bookable"] = (Availability_Slot.query.filter(Availability_Slot.supervisor_id.in_(sup_ids), Availability_Slot.booked_by.is_(None),
                                                          Availability_Slot.start_ts > now)
                           .order_by(Availability_Slot.start_ts.asc()).limit(40).all()) if sup_ids else []
        from superviseme.utils import calendar_feed as cf
        # slots overlapping the supervisor's external calendar are hidden (the reason is never disclosed)
        ctx["bookable"] = [sl for sl in ctx["bookable"] if not cf.conflicts(sl.supervisor_id, sl.start_ts, sl.end_ts)]
        ctx["has_thesis"] = bool(sup_ids)
    ctx["week"] = _week_view(request.args.get("week"), now, is_sup)
    ctx["feed_url"], ctx["feed_enabled"] = _feed_urls(current_user)
    return render_template("workflow/agenda.html", **ctx)


def _feed_urls(user):
    if not user.agenda_token:
        return None, False
    https_url = url_for("workflow.agenda_feed", token=user.agenda_token, _external=True)
    return https_url, True


def _week_view(raw, now, is_sup):
    """One week of the agenda: meetings, office-hour slots and (supervisors) external busy time."""
    from superviseme.utils import calendar_feed as cf
    monday, start, end = meeting_utils.week_bounds(raw)
    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        s0 = int(datetime(d.year, d.month, d.day).timestamp())
        n = d + timedelta(days=1)
        days.append({"date": d, "start": s0, "end": int(datetime(n.year, n.month, n.day).timestamp()), "events": [],
                     "is_today": d == date.today()})

    def put(ts, item):
        for day in days:
            if day["start"] <= ts < day["end"]:
                day["events"].append(item)
                return

    for m in meeting_utils.meetings_between(current_user, start, end):
        other = m.student if current_user.id == m.supervisor_id else m.supervisor
        put(m.start_ts, {"kind": "meeting", "start": m.start_ts, "end": m.end_ts, "title": m.title, "m": m, "other": other})
    if is_sup:
        busy = cf.busy_for(current_user.id, start, end) if cf.status(current_user.id) else []
        for sl in Availability_Slot.query.filter(Availability_Slot.supervisor_id == current_user.id, Availability_Slot.start_ts >= start,
                                                  Availability_Slot.start_ts < end, Availability_Slot.booked_by.is_(None)).all():
            put(sl.start_ts, {"kind": "slot", "start": sl.start_ts, "end": sl.end_ts, "slot": sl, "bookable": False,
                              "conflict": any(b[0] < sl.end_ts and b[1] > sl.start_ts for b in busy)})
        for b0, b1 in busy:
            # split overnight blocks so each day shows its own part
            for day in days:
                lo, hi = max(b0, day["start"]), min(b1, day["end"])
                if lo < hi:
                    day["events"].append({"kind": "busy", "start": lo, "end": hi})
    elif current_user.user_type == "student":
        sup_ids = meeting_utils.supervisors_of_student(current_user.id)
        if sup_ids:
            for sl in Availability_Slot.query.filter(Availability_Slot.supervisor_id.in_(sup_ids), Availability_Slot.booked_by.is_(None),
                                                      Availability_Slot.start_ts > now, Availability_Slot.start_ts >= start,
                                                      Availability_Slot.start_ts < end).all():
                if not cf.conflicts(sl.supervisor_id, sl.start_ts, sl.end_ts):
                    put(sl.start_ts, {"kind": "slot", "start": sl.start_ts, "end": sl.end_ts, "slot": sl, "bookable": True, "conflict": False})
    for day in days:
        day["events"].sort(key=lambda it: (it["start"], it["kind"]))
    horizon = date.today() + timedelta(days=cf.HORIZON_DAYS)
    return {"days": days, "monday": monday, "sunday": monday + timedelta(days=6),
            "prev": (monday - timedelta(days=7)).isoformat(), "next": (monday + timedelta(days=7)).isoformat(),
            "is_current": monday == date.today() - timedelta(days=date.today().weekday()),
            "beyond": is_sup and monday > horizon and bool(cf.status(current_user.id)), "horizon": horizon}


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
    try:
        call_url = clean_call_url(request.form.get("call_url"))
    except ValueError:
        flash(_("The call link must be a valid http(s) address."), "error")
        return _agenda_back()
    added = skipped = 0
    from superviseme.utils import calendar_feed as cf
    for w in range(repeat):
        for i in range(count):
            s = start + w * 7 * 86400 + i * minutes * 60
            exists = Availability_Slot.query.filter_by(supervisor_id=current_user.id, start_ts=s).first()
            if not exists and cf.conflicts(current_user.id, s, s + minutes * 60):
                skipped += 1
                continue
            if not exists:
                db.session.add(Availability_Slot(supervisor_id=current_user.id, start_ts=s, end_ts=s + minutes * 60,
                                                 location=location, call_url=call_url, created_at=int(time.time())))
                added += 1
    db.session.commit()
    flash(_("%(n)d slots published.", n=added), "success")
    if skipped:
        flash(_("%(n)d slots were skipped because you are busy in your external calendar.", n=skipped), "warning")
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
    from superviseme.utils import calendar_feed as cf
    if cf.conflicts(slot.supervisor_id, slot.start_ts, slot.end_ts):
        flash(_("Sorry, this slot is no longer available."), "error")
        return _agenda_back()
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
    try:
        call_url = clean_call_url(request.form.get("call_url"))
    except ValueError:
        flash(_("The call link must be a valid http(s) address."), "error")
        return _agenda_back()
    title = (request.form.get("title") or "").strip()[:200] or f"Meeting: {thesis.title}"[:200]
    m = Meeting(thesis_id=thesis.id, supervisor_id=current_user.id, student_id=thesis.author_id, title=title, start_ts=start,
                end_ts=start + minutes * 60, location=(request.form.get("location") or "").strip()[:200] or None,
                call_url=call_url, created_by=current_user.id, created_at=int(time.time()))
    from superviseme.utils import calendar_feed as cf
    clash = cf.conflicts(current_user.id, start, start + minutes * 60)
    db.session.add(m)
    db.session.commit()
    if clash:
        flash(_("Heads up: this time overlaps with an event in your external calendar."), "warning")
    from superviseme.utils.notifications import create_notification
    create_notification(thesis.author_id, current_user.id, "deadline_reminder", _("Meeting scheduled: %(t)s", t=title),
                        datetime.fromtimestamp(start).strftime("%d %b %Y, %H:%M") + (f" — {call_url}" if call_url else ""),
                        thesis_id=thesis.id)
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


def _meeting_dict(m, viewer=None):
    viewer = viewer or current_user
    other = m.student if viewer.id == m.supervisor_id else m.supervisor
    return {"uid": m.id, "title": m.title, "start": m.start_ts, "end": m.end_ts, "location": m.location, "url": m.call_url,
            "description": f"With {other.name} {other.surname}" if other else ""}


@workflow.route("/agenda/meetings/<int:meeting_id>/call", methods=["POST"])
@login_required
def set_meeting_call(meeting_id):
    m = _participant_meeting(meeting_id)
    if current_user.id != m.supervisor_id and current_user.user_type != "admin":
        abort(403)
    try:
        m.call_url = clean_call_url(request.form.get("call_url"))
    except ValueError:
        flash(_("The call link must be a valid http(s) address."), "error")
        return _agenda_back()
    db.session.commit()
    if m.student_id and m.call_url:
        from superviseme.utils.notifications import create_notification
        create_notification(m.student_id, current_user.id, "deadline_reminder", _("Call link added: %(t)s", t=m.title), m.call_url,
                            thesis_id=m.thesis_id)
    flash(_("Call link saved."), "success")
    return _agenda_back()


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


@workflow.route("/agenda/feed/<token>.ics")
def agenda_feed(token):
    """Subscribable iCal feed (Google, Apple, Outlook...). The unguessable token is the credential."""
    import secrets as _secrets
    user = User_mgmt.query.filter_by(agenda_token=token).first() if 20 <= len(token) <= 64 else None
    if not user or not user.is_enabled or not _secrets.compare_digest(user.agenda_token, token):
        abort(404)
    rows = [_meeting_dict(m, viewer=user) for m in meeting_utils.feed_meetings(user)]
    body = build_calendar(rows, name="SuperviseMe")
    return Response(body, mimetype="text/calendar", headers={
        "Cache-Control": "private, max-age=300", "X-Robots-Tag": "noindex, nofollow", "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer"})


@workflow.route("/agenda/feed/token", methods=["POST"])
@login_required
def agenda_feed_token():
    """Create, rotate or revoke the personal feed token."""
    import secrets
    action = request.form.get("action")
    user = User_mgmt.query.get(current_user.id)
    if action in ("create", "regenerate"):
        user.agenda_token = secrets.token_urlsafe(32)
        flash(_("Calendar subscription link created.") if action == "create" else _("A new link was generated; the old one no longer works."), "success")
    elif action == "revoke":
        user.agenda_token = None
        flash(_("Calendar subscription disabled."), "success")
    db.session.commit()
    return redirect(url_for("workflow.agenda") + "#subscribe")


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


# ---------------------------------------------------------------- end-of-thesis checklist
from superviseme.models import Checklist_Template, Checklist_Template_Item, Thesis_Checklist_Item  # noqa: E402
from superviseme.utils import checklist as cl  # noqa: E402


def _admin_only():
    if current_user.user_type != "admin":
        abort(403)


@workflow.route("/admin/checklists")
@login_required
def checklist_templates():
    _admin_only()
    return render_template("workflow/checklist_templates.html", templates=Checklist_Template.query.order_by(Checklist_Template.name).all())


@workflow.route("/admin/checklists/add", methods=["POST"])
@login_required
def add_checklist_template():
    _admin_only()
    name = (request.form.get("name") or "").strip()[:150]
    items = cl.parse_items(request.form.get("items"))
    if not name or not items:
        flash(_("A name and at least one step are required."), "error")
        return redirect(url_for("workflow.checklist_templates"))
    t = Checklist_Template(name=name, degree_course=(request.form.get("degree_course") or "").strip()[:120] or None,
                           created_at=int(time.time()))
    for pos, (title, days) in enumerate(items):
        t.items.append(Checklist_Template_Item(title=title, position=pos, days_before_defense=days))
    db.session.add(t)
    db.session.commit()
    flash(_("Template created."), "success")
    return redirect(url_for("workflow.checklist_templates"))


@workflow.route("/admin/checklists/<int:template_id>/delete", methods=["POST"])
@login_required
def delete_checklist_template(template_id):
    _admin_only()
    db.session.delete(Checklist_Template.query.get_or_404(template_id))
    db.session.commit()
    flash(_("Template deleted."), "success")
    return redirect(url_for("workflow.checklist_templates"))


@workflow.route("/thesis/<int:thesis_id>/checklist/apply", methods=["POST"])
@login_required
def apply_checklist_template(thesis_id):
    thesis, _role = load_thesis_or_403(current_user, thesis_id, roles=("admin", "supervisor"))
    template = Checklist_Template.query.get_or_404(request.form.get("template_id", type=int) or 0)
    added = cl.apply_template(thesis, template)
    flash(_("%(n)d steps added.", n=added), "success")
    return _team_back(thesis)


@workflow.route("/thesis/<int:thesis_id>/checklist/settings", methods=["POST"])
@login_required
def checklist_settings(thesis_id):
    thesis, _role = load_thesis_or_403(current_user, thesis_id, roles=("admin", "supervisor"))
    raw = (request.form.get("defense_date") or "").strip()
    if raw and parse_date(raw) is None:
        flash(_("Invalid date."), "error")
        return _team_back(thesis)
    thesis.defense_date = parse_date(raw) if raw else None
    thesis.degree_course = (request.form.get("degree_course") or "").strip()[:120] or None
    cl.recompute_due_dates(thesis)
    db.session.commit()
    flash(_("Checklist settings saved."), "success")
    return _team_back(thesis)


@workflow.route("/thesis/<int:thesis_id>/checklist/add", methods=["POST"])
@login_required
def add_checklist_item(thesis_id):
    thesis, _role = load_thesis_or_403(current_user, thesis_id, roles=("admin", "supervisor"))
    title = (request.form.get("title") or "").strip()[:200]
    due = parse_date(request.form.get("due_date"))
    if not title or len(thesis.checklist) >= cl.MAX_ITEMS:
        flash(_("A title is required."), "error")
        return _team_back(thesis)
    pos = max([i.position for i in thesis.checklist] + [-1]) + 1
    db.session.add(Thesis_Checklist_Item(thesis_id=thesis.id, title=title, position=pos, due_date=due, created_at=int(time.time())))
    db.session.commit()
    return _team_back(thesis)


def _item_for(item_id, roles):
    item = Thesis_Checklist_Item.query.get_or_404(item_id)
    thesis, role = load_thesis_or_403(current_user, item.thesis_id, roles=roles)
    return item, thesis


@workflow.route("/checklist/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_checklist_item(item_id):
    item, thesis = _item_for(item_id, ("admin", "supervisor", "student"))
    if item.status == "done":
        item.status, item.completed_at, item.completed_by = "pending", None, None
    else:
        item.status, item.completed_at, item.completed_by = "done", int(time.time()), current_user.id
    db.session.commit()
    return _team_back(thesis)


@workflow.route("/checklist/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_checklist_item(item_id):
    item, thesis = _item_for(item_id, ("admin", "supervisor"))
    db.session.delete(item)
    db.session.commit()
    return _team_back(thesis)


# ---------------------------------------------------------------- global search
@workflow.route("/search")
@login_required
def search():
    from superviseme.utils import search as search_utils
    term = (request.args.get("q") or "").strip()[:100]
    results = search_utils.search(current_user, term)
    thesis_ids = {x.thesis_id for key in ("updates", "tasks", "notes", "documents") for x in results[key]}
    theses = {t.id: t for t in Thesis.query.filter(Thesis.id.in_(thesis_ids)).all()} if thesis_ids else {}

    def note_url(note):
        endpoint = {"student": "student.meeting_note_detail", "supervisor": "supervisor.meeting_note_detail",
                    "researcher": "researcher.supervisor_meeting_note_detail"}.get(current_user.user_type)
        return url_for(endpoint, note_id=note.id) if endpoint else thesis_url(current_user, theses[note.thesis_id])

    def thesis_link(t):
        if thesis_role(current_user, t):
            return thesis_url(current_user, t)
        return url_for("public.public_thesis_detail", thesis_id=t.id)

    total = sum(len(v) for v in results.values())
    return render_template("workflow/search.html", term=term, results=results, theses=theses, total=total,
                           note_url=note_url, thesis_link=thesis_link, snippet=search_utils.snippet,
                           min_len=search_utils.MIN_LEN, thesis_url=thesis_url)


# ---------------------------------------------------------------- reports and archive
from superviseme.utils import reports as rp  # noqa: E402


def _period():
    since, until = parse_date(request.args.get("from")), parse_date(request.args.get("to"))
    if until is not None:
        until += 86400  # inclusive end day
    return since, until


def _download(body, mimetype, filename):
    resp = Response(body, mimetype=mimetype)
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@workflow.route("/thesis/<int:thesis_id>/report.<fmt>")
@login_required
def thesis_report(thesis_id, fmt):
    if fmt not in ("csv", "pdf"):
        abort(404)
    thesis, _role = load_thesis_or_403(current_user, thesis_id)
    since, until = _period()
    data = rp.thesis_report(thesis, since, until)
    name = f"thesis-{thesis.id}-report.{fmt}"
    if fmt == "csv":
        return _download(rp.report_csv(data), "text/csv; charset=utf-8", name)
    try:
        return _download(rp.report_pdf(data), "application/pdf", name)
    except ImportError:
        abort(501)


@workflow.route("/reports")
@login_required
def reports():
    if current_user.user_type not in ("admin", "supervisor", "researcher"):
        abort(403)
    theses = rp.theses_for_reports(current_user)
    concluded = [t for t in theses if rp.is_concluded(t)]
    active = [t for t in theses if t not in concluded]
    return render_template("workflow/reports.html", active=active, concluded=concluded, status=rp.latest_status,
                           dt=datetime.fromtimestamp)


@workflow.route("/reports/activity.csv")
@login_required
def activity_report():
    if current_user.user_type not in ("admin", "supervisor", "researcher"):
        abort(403)
    since, until = _period()
    only = (request.args.get("scope") or "all")
    theses = rp.theses_for_reports(current_user)
    if only == "concluded":
        theses = [t for t in theses if rp.is_concluded(t)]
    elif only == "active":
        theses = [t for t in theses if not rp.is_concluded(t)]
    return _download(rp.activity_csv([rp.thesis_report(t, since, until) for t in theses]), "text/csv; charset=utf-8", "activity-report.csv")


# ---------------------------------------------------------------- privacy / GDPR
import json  # noqa: E402

from flask_login import logout_user  # noqa: E402
from superviseme.models import Profile_View  # noqa: E402
from superviseme.utils import privacy as pv  # noqa: E402


@workflow.route("/privacy")
@login_required
def privacy():
    """The privacy controls live in the last tab of the profile page."""
    return redirect(url_for("profile.profile_page") + "#tabPrivacy")


@workflow.route("/privacy/export.json")
@login_required
def privacy_export():
    body = json.dumps(pv.export_user_data(current_user), indent=2, ensure_ascii=False, default=str)
    return _download(body, "application/json; charset=utf-8", f"my-data-{current_user.id}.json")


@workflow.route("/privacy/delete", methods=["POST"])
@login_required
def privacy_delete():
    if pv.erasure_blockers(current_user):
        flash(_("Your account cannot be erased right now."), "error")
        return redirect(url_for("workflow.privacy"))
    if (request.form.get("confirm") or "").strip() != current_user.username:
        flash(_("Type your username to confirm."), "error")
        return redirect(url_for("workflow.privacy"))
    user = User_mgmt.query.get(current_user.id)
    logout_user()
    pv.anonymize_user(user)
    flash(_("Your personal data was erased."), "success")
    return redirect(url_for("auth.login"))


@workflow.route("/admin/privacy", methods=["GET", "POST"])
@login_required
def admin_privacy():
    _admin_only()
    purged = pv.purge_expired() if request.method == "POST" else None
    return render_template("workflow/admin_privacy.html", months=pv.retention_months(), purged=purged)


# ---------------------------------------------------------------- external calendar (iCal feed)
@workflow.route("/agenda/calendar/connect", methods=["POST"])
@login_required
def connect_calendar():
    if not _is_supervisor():
        abort(403)
    from superviseme.utils import calendar_feed as cf
    try:
        cf.connect(current_user, request.form.get("url"))
        flash(_("Calendar connected."), "success")
    except cf.FeedError as exc:
        flash(_(str(exc)), "error")
    return _agenda_back()


@workflow.route("/agenda/calendar/refresh", methods=["POST"])
@login_required
def refresh_calendar():
    if not _is_supervisor():
        abort(403)
    from superviseme.models import Calendar_Feed
    from superviseme.utils import calendar_feed as cf
    feed = Calendar_Feed.query.filter_by(user_id=current_user.id).first()
    if feed:
        cf.refresh(feed, force=True)
        flash(_("Calendar updated.") if not feed.last_error else _(feed.last_error), "success" if not feed.last_error else "error")
    return _agenda_back()


@workflow.route("/agenda/calendar/disconnect", methods=["POST"])
@login_required
def disconnect_calendar():
    if not _is_supervisor():
        abort(403)
    from superviseme.utils import calendar_feed as cf
    cf.disconnect(current_user)
    flash(_("Calendar disconnected."), "success")
    return _agenda_back()
