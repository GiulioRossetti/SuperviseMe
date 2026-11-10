"""Supervision capacity: how many active students a supervisor takes on."""
from superviseme import db
from superviseme.models import Thesis, Thesis_Supervisor, User_mgmt


def active_student_count(supervisor_id):
    return (
        db.session.query(db.func.count(db.distinct(Thesis.id)))
        .join(Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id)
        .filter(Thesis_Supervisor.supervisor_id == supervisor_id, Thesis_Supervisor.role == "supervisor",
                Thesis.author_id.isnot(None), Thesis.frozen.isnot(True))
        .scalar()
    ) or 0


def capacity_info(user):
    used = active_student_count(user.id)
    limit = user.max_students
    return {"used": used, "max": limit, "full": limit is not None and used >= limit,
            "left": None if limit is None else max(0, limit - used)}


def full_supervisors(thesis):
    """Primary supervisors of ``thesis`` who have no free capacity left."""
    out = []
    for ts in Thesis_Supervisor.query.filter_by(thesis_id=thesis.id, role="supervisor").all():
        user = db.session.get(User_mgmt, ts.supervisor_id)
        if user and capacity_info(user)["full"]:
            out.append(user)
    return out


def capacity_message(thesis):
    """Human message when assigning a student to ``thesis`` would exceed a supervisor's limit, else None."""
    blocked = full_supervisors(thesis)
    if not blocked:
        return None
    names = ", ".join(f"{u.name} {u.surname} ({u.max_students})" for u in blocked)
    return f"Supervision capacity reached: {names}. Raise the limit in the profile or free a place first."


# ------------------------------------------------------------------ one active thesis per student
def active_thesis_for(student_id, exclude_thesis_id=None):
    """The student's current (not archived, not completed) thesis, or None."""
    from superviseme.utils.reports import is_concluded

    if not student_id:
        return None
    for thesis in Thesis.query.filter_by(author_id=student_id).all():
        if thesis.id != exclude_thesis_id and not is_concluded(thesis):
            return thesis
    return None


def student_has_active_thesis(user):
    return bool(getattr(user, "is_authenticated", False)) and user.user_type == "student" and active_thesis_for(user.id) is not None


def active_thesis_message(student_id, exclude_thesis_id=None):
    """Message when ``student_id`` already has an active thesis (a student can only have one), else None."""
    if active_thesis_for(student_id, exclude_thesis_id):
        return "This student already has an active thesis: complete or archive it before assigning another one."
    return None
