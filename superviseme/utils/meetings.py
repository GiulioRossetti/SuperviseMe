"""Meeting helpers: listing, reminders and booking rules."""
import time
from datetime import datetime

from sqlalchemy import or_

from superviseme import db
from superviseme.models import Availability_Slot, Meeting, Thesis_Supervisor

DAY = 86400


def meetings_for(user, upcoming=True, limit=50):
    q = Meeting.query.filter(Meeting.status == "scheduled")
    if user.user_type != "admin":
        q = q.filter(or_(Meeting.supervisor_id == user.id, Meeting.student_id == user.id))
    now = int(time.time())
    if upcoming:
        q = q.filter(Meeting.end_ts >= now).order_by(Meeting.start_ts.asc())
    else:
        q = q.filter(Meeting.end_ts < now).order_by(Meeting.start_ts.desc())
    return q.limit(limit).all()


def supervisors_of_student(student_id):
    from superviseme.models import Thesis
    ids = {
        ts.supervisor_id
        for ts in Thesis_Supervisor.query.join(Thesis, Thesis.id == Thesis_Supervisor.thesis_id)
        .filter(Thesis.author_id == student_id).all()
    }
    return ids


def book_slot(slot_id, student, thesis):
    """Atomically book a slot; returns the Meeting or None if the slot was taken."""
    now = int(time.time())
    updated = Availability_Slot.query.filter(
        Availability_Slot.id == slot_id, Availability_Slot.booked_by.is_(None), Availability_Slot.start_ts > now
    ).update({"booked_by": student.id}, synchronize_session=False)
    if updated != 1:
        db.session.rollback()
        return None
    slot = Availability_Slot.query.get(slot_id)
    meeting = Meeting(
        thesis_id=thesis.id, supervisor_id=slot.supervisor_id, student_id=student.id,
        title=f"Meeting: {thesis.title}"[:200], start_ts=slot.start_ts, end_ts=slot.end_ts,
        location=slot.location, slot_id=slot.id, created_by=student.id, created_at=now,
    )
    db.session.add(meeting)
    db.session.commit()
    return meeting


def cancel_meeting(meeting):
    meeting.status = "cancelled"
    if meeting.slot_id:
        slot = Availability_Slot.query.get(meeting.slot_id)
        if slot and slot.start_ts > time.time():
            slot.booked_by = None  # the slot becomes bookable again
    db.session.commit()


def meeting_reminders(now, notify):
    """Remind both participants of meetings starting within 24h (called by run_reminders)."""
    sent = 0
    for m in Meeting.query.filter(Meeting.status == "scheduled", Meeting.start_ts >= now, Meeting.start_ts <= now + DAY).all():
        when = datetime.fromtimestamp(m.start_ts).strftime("%d %b %Y, %H:%M")
        place = f" — {m.location}" if m.location else ""
        for uid in {m.supervisor_id, m.student_id} - {None}:
            sent += notify(uid, "meeting", m.id, "day", f"Meeting tomorrow: {m.title}", f"{when}{place}", m.thesis_id)
    return sent
