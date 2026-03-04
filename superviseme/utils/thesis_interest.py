import time

from superviseme.models import Thesis_Interest


TERMINAL_STATUSES = {"accepted", "declined", "closed"}


def accept_interest_and_close_others(thesis_id, accepted_interest_id, handler_id):
    now = int(time.time())
    pending = Thesis_Interest.query.filter_by(thesis_id=thesis_id, status="pending").all()
    for interest in pending:
        if interest.id == accepted_interest_id:
            interest.status = "accepted"
        else:
            interest.status = "closed"
        interest.handled_at = now
        interest.handled_by_id = handler_id


def close_interests_after_direct_assignment(thesis_id, assigned_student_id, handler_id):
    now = int(time.time())
    pending = Thesis_Interest.query.filter_by(thesis_id=thesis_id, status="pending").all()
    for interest in pending:
        if interest.student_id == assigned_student_id:
            interest.status = "accepted"
        else:
            interest.status = "closed"
        interest.handled_at = now
        interest.handled_by_id = handler_id


def decline_interest(interest, handler_id):
    if interest.status != "pending":
        return
    interest.status = "declined"
    interest.handled_at = int(time.time())
    interest.handled_by_id = handler_id
