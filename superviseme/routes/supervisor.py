from flask import Blueprint, request, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload
from superviseme.utils import security
from superviseme.utils.miscellanea import check_privileges
from superviseme.utils.activity_tracker import get_inactive_students
from superviseme.models import *
from superviseme import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from superviseme.utils.thesis_timeline import build_status_timeline, build_activity_calendar
import time
from flask_babel import gettext as _

supervisor = Blueprint("supervisor", __name__)


@supervisor.route("/supervisor/dashboard")
@login_required
def dashboard():
    """
    This route is for admin data. It retrieves all users from the database
    and renders them in a template.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    from superviseme.utils.dashboard_data import supervisor_overview
    return render_template("/supervisor/supervisor_dashboard.html", current_user=current_user,
                           ov=supervisor_overview(current_user), dt=datetime.fromtimestamp, str=str)


@supervisor.route("/supervisor/supervisee")
@login_required
def supervisee_data():
    """
    This route is for supervisee data. It retrieves all supervisees from the database
    and renders them in a template.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Get students through thesis supervision relationship
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id)\
        .options(joinedload(Thesis_Supervisor.thesis).joinedload(Thesis.author))\
        .all()
    active_supervisees = []
    past_supervisees = []
    
    # Get inactive students data
    inactive_data = get_inactive_students(current_user.id)
    inactive_dict = {data['student'].id: data for data in inactive_data}
    
    now = int(time.time())
    for ts in thesis_supervisors:
        if ts.thesis and ts.thesis.author:
            student_data = inactive_dict.get(ts.thesis.author.id, {})
            thesis = ts.thesis
            latest_status = (
                Thesis_Status.query.filter_by(thesis_id=thesis.id)
                .order_by(Thesis_Status.updated_at.desc()).first()
            )
            todos_total = Todo.query.filter_by(thesis_id=thesis.id).count()
            todos_done = Todo.query.filter_by(thesis_id=thesis.id, status="completed").count()
            last_update = (
                Thesis_Update.query.filter_by(thesis_id=thesis.id, author_id=thesis.author.id)
                .order_by(Thesis_Update.created_at.desc()).first()
            )

            supervisee_info = {
                'student': thesis.author,
                'thesis': thesis,
                'is_inactive': student_data.get('is_inactive', False),
                'days_inactive': student_data.get('days_inactive'),
                'last_activity_location': student_data.get('last_activity_location'),
                'status': latest_status.status if latest_status else None,
                'todos_total': todos_total,
                'todos_done': todos_done,
                'progress': int(round(100 * todos_done / todos_total)) if todos_total else None,
                'last_update_at': last_update.created_at if last_update else None,
                'never_logged': thesis.author.last_activity is None,
                'topic': thesis.topic,
                'keywords': [t.tag for t in thesis.tags],
            }

            # Separate active and archived/frozen theses
            if ts.thesis.frozen:
                past_supervisees.append(supervisee_info)
            else:
                active_supervisees.append(supervisee_info)

    # Fix "Inactive for None days" issue by providing a default value
    for supervisee in active_supervisees + past_supervisees:
        if supervisee['days_inactive'] is None:
            supervisee['days_inactive'] = 'Unknown'

    active_supervisees.sort(key=lambda i: ((i['student'].surname or '').lower(), (i['student'].name or '').lower()))

    return render_template("supervisor/supervisees.html", 
                         supervisees=active_supervisees, 
                         past_supervisees=past_supervisees)


# --- Student profile (supervisor view) --------------------------------------

STUDENT_EDIT_UNLOCK_SECONDS = 10 * 60


UNLOCK_MAX_FAILURES = 5


UNLOCK_LOCKOUT_SECONDS = 5 * 60


def _supervised_student_or_none(student_id):
    """Return the student only if they author a thesis supervised by the current user."""
    return User_mgmt.query.join(Thesis, Thesis.author_id == User_mgmt.id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        User_mgmt.id == student_id,
        User_mgmt.user_type == "student",
        Thesis_Supervisor.supervisor_id == current_user.id,
    ).first()


def _student_edit_unlocked(student_id):
    expiry = (session.get("student_edit_unlock") or {}).get(str(student_id))
    return bool(expiry and expiry > time.time())


@supervisor.route("/supervisor/student/<int:student_id>")
@login_required
def student_profile(student_id):
    """Read-only profile of a supervised student (editing requires password confirmation)."""
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    student = _supervised_student_or_none(student_id)
    if not student:
        flash(_("Student not found or not supervised by you"))
        return redirect(url_for('supervisor.supervisee_data'))

    from superviseme.utils.privacy import log_profile_view
    log_profile_view(current_user, student)

    theses = (
        Thesis.query.join(Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id)
        .filter(Thesis.author_id == student.id, Thesis_Supervisor.supervisor_id == current_user.id)
        .order_by(Thesis.created_at.desc()).all()
    )
    thesis_ids = [t.id for t in theses]
    updates = Thesis_Update.query.filter(Thesis_Update.thesis_id.in_(thesis_ids)).all() if thesis_ids else []
    todos = Todo.query.filter(Todo.thesis_id.in_(thesis_ids)).all() if thesis_ids else []
    notes = MeetingNote.query.filter(MeetingNote.thesis_id.in_(thesis_ids)).all() if thesis_ids else []
    events = [u.created_at for u in updates if u.author_id == student.id]
    events += [n.created_at for n in notes if n.author_id == student.id]
    events += [t.created_at for t in todos if t.author_id == student.id]
    events += [t.completed_at for t in todos if t.completed_at and t.assigned_to_id in (None, student.id)]

    statuses = {}
    for t in theses:
        sts = Thesis_Status.query.filter_by(thesis_id=t.id).all()
        statuses[t.id] = build_status_timeline(sts)

    now = int(time.time())
    expiry = (session.get("student_edit_unlock") or {}).get(str(student.id), 0)
    return render_template(
        "supervisor/student_profile.html",
        student=student,
        theses=theses,
        statuses=statuses,
        recent_updates=sorted([u for u in updates if u.author_id == student.id and u.parent_id is None],
                              key=lambda u: u.created_at, reverse=True)[:5],
        todos_total=len(todos),
        todos_done=len([t for t in todos if t.status == "completed"]),
        notes_count=len(notes),
        updates_count=len([u for u in updates if u.author_id == student.id]),
        activity_calendar=build_activity_calendar(events),
        unlocked=expiry > now,
        unlock_remaining=max(0, int((expiry - now) / 60)) if expiry > now else 0,
        dt=datetime.fromtimestamp,
    )


@supervisor.route("/supervisor/student/<int:student_id>/unlock", methods=["POST"])
@login_required
def unlock_student_edit(student_id):
    """Re-authenticate the supervisor with their own password to enable editing for a few minutes."""
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    if not _supervised_student_or_none(student_id):
        flash(_("Student not found or not supervised by you"))
        return redirect(url_for('supervisor.supervisee_data'))

    now = time.time()
    lock_until = session.get("student_unlock_lock_until", 0)
    if lock_until > now:
        flash(_("Too many failed attempts. Please try again in a few minutes."))
        return redirect(url_for('supervisor.student_profile', student_id=student_id))

    password = request.form.get("password") or ""
    if not check_password_hash(current_user.password, password):
        failures = session.get("student_unlock_failures", 0) + 1
        session["student_unlock_failures"] = failures
        if failures >= UNLOCK_MAX_FAILURES:
            session["student_unlock_lock_until"] = now + UNLOCK_LOCKOUT_SECONDS
            session["student_unlock_failures"] = 0
        flash(_("Incorrect password."))
        return redirect(url_for('supervisor.student_profile', student_id=student_id))

    session["student_unlock_failures"] = 0
    unlocks = dict(session.get("student_edit_unlock") or {})
    unlocks[str(student_id)] = now + STUDENT_EDIT_UNLOCK_SECONDS
    session["student_edit_unlock"] = unlocks
    flash(_("Editing unlocked for 10 minutes."))
    return redirect(url_for('supervisor.student_profile', student_id=student_id))


@supervisor.route("/supervisor/student/<int:student_id>/lock", methods=["POST"])
@login_required
def lock_student_edit(student_id):
    unlocks = dict(session.get("student_edit_unlock") or {})
    unlocks.pop(str(student_id), None)
    session["student_edit_unlock"] = unlocks
    return redirect(url_for('supervisor.student_profile', student_id=student_id))


@supervisor.route("/supervisor/add_supervisee", methods=["POST"])
@login_required
def add_supervisee():
    """
    This route handles adding a supervisee to the current supervisor. It retrieves the necessary data from the form,
    creates a new Thesis_Supervisor object, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    supervisee_id = request.form.get("supervisee_id")
    thesis = Thesis.query.filter_by(author_id=supervisee_id).first()
    if not thesis:
        return supervisee_data()

    existing_supervisee = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis.id, supervisor_id=current_user.id
    ).first()
    if existing_supervisee:
        return supervisee_data()

    new_supervisee = Thesis_Supervisor(
        thesis_id=thesis.id,
        supervisor_id=current_user.id,
        assigned_at=int(time.time())
    )
    db.session.add(new_supervisee)
    db.session.commit()
    return supervisee_data()


@supervisor.route("/supervisor/remove_supervisee/<int:supervisee_id>", methods=["POST"])
@login_required
def remove_supervisee(supervisee_id):
    """
    This route handles removing a supervisee from the current supervisor. It retrieves the Thesis_Supervisor object,
    deletes it from the database, and redirects to the supervisee data page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    thesis = Thesis.query.filter_by(author_id=supervisee_id).first()
    if not thesis:
        return supervisee_data()

    supervisee = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis.id, supervisor_id=current_user.id
    ).first()
    if supervisee:
        db.session.delete(supervisee)
        db.session.commit()

    return supervisee_data()


@supervisor.route("/supervisor/delete_supervisee/<int:supervisee_id>", methods=["POST"])
@login_required
def delete_supervisee(supervisee_id):
    """
    This route handles deleting a supervisee by their ID. It retrieves the Thesis_Supervisor object,
    deletes it from the database, and redirects to the supervisee data page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    supervisee = Thesis_Supervisor.query.filter_by(
        id=supervisee_id, supervisor_id=current_user.id
    ).first()
    if supervisee:
        db.session.delete(supervisee)
        db.session.commit()

    return supervisee_data()


@supervisor.route("/supervisor/search", methods=["POST"])
@login_required
def search():
    """
    This route handles searching for theses or supervisees. It retrieves the search term from the form,
    performs a search in the database, and returns the results.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    search_term = request.form.get("search_term", "").strip()

    # Validate search term
    if not search_term:
        # If no search term, redirect back to dashboard with message
        from flask import flash, redirect, url_for
        flash("Please enter a search term.", "warning")
        return redirect(url_for('supervisor.dashboard'))

    # Search for theses supervised by current user
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).all()
    supervised_thesis_ids = [ts.thesis_id for ts in thesis_supervisors]
    
    theses = []
    supervisees = []
    
    if search_term:
        # Search for supervised theses
        theses = Thesis.query.filter(
            and_(
                Thesis.id.in_(supervised_thesis_ids),
                or_(
                    Thesis.title.ilike(f"%{search_term}%"),
                    Thesis.description.ilike(f"%{search_term}%"),
                    Thesis.level.ilike(f"%{search_term}%")
                )
            )
        ).all()

        # Search for supervisees (students with supervised theses)
        supervised_student_ids = [thesis.author_id for thesis in Thesis.query.filter(Thesis.id.in_(supervised_thesis_ids)).all() if thesis.author_id]
        supervisees = User_mgmt.query.filter(
            and_(
                User_mgmt.id.in_(supervised_student_ids),
                or_(
                    User_mgmt.name.ilike(f"%{search_term}%"),
                    User_mgmt.surname.ilike(f"%{search_term}%"),
                    User_mgmt.username.ilike(f"%{search_term}%"),
                    User_mgmt.email.ilike(f"%{search_term}%")
                )
            )
        ).all()

    return render_template("supervisor/search_results.html", 
                         theses=theses, 
                         supervisees=supervisees,
                         search_term=search_term,
                         user_type="supervisor")


# Student management routes for supervisors
@supervisor.route("/supervisor/create_student", methods=["POST"])
@login_required
def create_student():
    """
    This route allows supervisors to create new student accounts.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    email = request.form.get("email")
    username = request.form.get("username")
    name = request.form.get("name")
    surname = request.form.get("surname")
    cdl = request.form.get("cdl")
    gender = request.form.get("gender")
    nationality = request.form.get("nationality")
    password = request.form.get("password")
    password2 = request.form.get("password2")

    # Validation
    if User_mgmt.query.filter_by(email=email).first():
        flash("Email address already exists")
        return redirect(request.referrer)

    if User_mgmt.query.filter_by(username=username).first():
        flash("Username already exists")
        return redirect(request.referrer)

    if password != password2:
        flash("Passwords do not match")
        return redirect(request.referrer)

    pw_error = security.validate_password(password)
    if pw_error:
        flash(pw_error)
        return redirect(request.referrer)

    # Create new student
    new_student = User_mgmt(
        email=email,
        username=username,
        password=generate_password_hash(password, method="pbkdf2:sha256"),
        name=name,
        surname=surname,
        cdl=cdl,
        nationality=nationality,
        gender=gender,
        user_type="student",
        joined_on=int(time.time()),
    )
    
    db.session.add(new_student)
    db.session.commit()
    flash(f"Student {name} {surname} created successfully")
    
    return redirect(url_for('supervisor.supervisee_data'))


@supervisor.route("/supervisor/edit_student/<int:student_id>", methods=["POST"])
@login_required
def edit_student(student_id):
    """
    This route allows supervisors to edit student accounts they supervise.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this student
    student = User_mgmt.query.join(Thesis, Thesis.author_id == User_mgmt.id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        User_mgmt.id == student_id,
        User_mgmt.user_type == "student",
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not student:
        flash(_("Student not found or not supervised by you"))
        return redirect(url_for('supervisor.supervisee_data'))

    if not _student_edit_unlocked(student.id):
        flash(_("Please confirm your password to edit this student's profile."))
        return redirect(url_for('supervisor.student_profile', student_id=student.id))

    new_email = (request.form.get("email") or student.email).strip()
    if new_email != student.email and User_mgmt.query.filter(
        User_mgmt.email == new_email, User_mgmt.id != student.id
    ).first():
        flash("Email address already exists")
        return redirect(url_for('supervisor.student_profile', student_id=student.id))

    # Update student information
    student.name = request.form.get("name", student.name)
    student.surname = request.form.get("surname", student.surname)
    student.email = new_email
    student.cdl = request.form.get("cdl", student.cdl)
    student.gender = request.form.get("gender", student.gender)
    student.nationality = request.form.get("nationality", student.nationality)
    
    # Only update password if provided
    new_password = request.form.get("password")
    if new_password:
        password2 = request.form.get("password2")
        if new_password != password2:
            flash("Passwords do not match")
            return redirect(url_for('supervisor.student_profile', student_id=student.id))
        pw_error = security.validate_password(new_password)
        if pw_error:
            flash(pw_error)
            return redirect(url_for('supervisor.student_profile', student_id=student.id))
        student.password = generate_password_hash(new_password, method="pbkdf2:sha256")
    
    db.session.commit()
    flash(f"Student {student.name} {student.surname} updated successfully")
    
    return redirect(url_for('supervisor.student_profile', student_id=student.id))


@supervisor.route("/supervisor/delete_student/<int:student_id>", methods=["POST", "DELETE"])
@login_required
def delete_student(student_id):
    """
    This route allows supervisors to delete student accounts they supervise.
    Only students with no active thesis assignments can be deleted.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this student
    student = User_mgmt.query.join(Thesis, Thesis.author_id == User_mgmt.id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        User_mgmt.id == student_id,
        User_mgmt.user_type == "student",
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not student:
        flash(_("Student not found or not supervised by you"))
        return redirect(url_for('supervisor.supervisee_data'))
    
    # Check if student has any active theses (only allow deletion if no active theses)
    active_theses = Thesis.query.filter_by(author_id=student_id, frozen=False).count()
    if active_theses > 0:
        flash(f"Cannot delete student {student.name} {student.surname}. Student has active thesis assignments.")
        return redirect(url_for('supervisor.supervisee_data'))
    
    try:
        # Remove thesis assignments (set author_id to None for completed/frozen theses)
        Thesis.query.filter_by(author_id=student_id).update({"author_id": None})
        
        # Delete the student
        db.session.delete(student)
        db.session.commit()
        flash(f"Student {student.name} {student.surname} deleted successfully")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting student: {e}")
    
    return redirect(url_for('supervisor.supervisee_data'))


# Domain modules register their routes on the same blueprint (and are re-exported for shared views).
from superviseme.routes.supervisor_theses import *  # noqa: E402,F401,F403
from superviseme.routes.supervisor_workspace import *  # noqa: E402,F401,F403
