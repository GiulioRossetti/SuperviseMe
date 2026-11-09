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
        user = User_mgmt.query.get(ts.supervisor_id)
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
