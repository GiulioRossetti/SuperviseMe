from collections import defaultdict

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import aliased
from werkzeug.security import generate_password_hash
from superviseme.models import *
from superviseme.utils.miscellanea import check_privileges
from superviseme import db
from datetime import datetime
import time

admin = Blueprint("admin", __name__)


@admin.route("/admin/dashboard")
@login_required
def dashboard():
    """
    This route is for admin data. It retrieves all users from the database
    and renders them in a template.
    """
    check_privileges(current_user.username, role="admin")

    # count all users by their user_type
    user_counts = {
        "students": User_mgmt.query.filter_by(user_type="student").count(),
        "supervisors": User_mgmt.query.filter_by(user_type="supervisor").count(),
        "admins": User_mgmt.query.filter_by(user_type="admin").count(),
    }

    # count all theses by their status
    thesis_counts = {
        "total": Thesis.query.count(),
    }

    supervisors = User_mgmt.query.filter_by(user_type="supervisor").all()

    # for each supervisor get list of theses assigned to them along with the name of the student
    theses_by_supervisor = {}
    for supervisor in supervisors:
        theses = Thesis_Supervisor.query.filter_by(supervisor_id=supervisor.id).all()
        theses_by_supervisor[supervisor] = [
                    {
                        "thesis": Thesis.query.filter(Thesis.id == thesis.id, Thesis.author_id.isnot(None)).first(),
                        "student": db.session.execute(
                                    select(User_mgmt)
                                    .join(Thesis, Thesis.author_id == User_mgmt.id)
                                    .where(
                                        and_(Thesis.id == thesis.id, Thesis.author_id.isnot(None))
                                    )
                                ).scalars().first()
                    } for thesis in theses
                ]
    # filter out theses that have no student assigned
    theses_by_supervisor = {
        supervisor: [t for t in theses if t["student"] is not None]
        for supervisor, theses in theses_by_supervisor.items()
    }

    # for each supervisor get the list of available theses not assigned to students
    available_theses_by_supervisor = defaultdict(list)
    available_theses = Thesis.query.filter(Thesis.author_id.is_(None)).all()
    for supervisor in supervisors:
        available_theses_by_supervisor[supervisor].extend(
            [{"thesis": thesis} for thesis in available_theses]
        )

    return render_template("/admin/admin_dashboard.html", current_user=current_user,
                           user_counts=user_counts, thesis_counts=thesis_counts,
                           theses_by_supervisor=theses_by_supervisor, available_theses=available_theses_by_supervisor, dt=datetime.fromtimestamp, str=str)


@admin.route("/admin/users")
@login_required
def users():
    """
    This route renders the form for creating a new user. It checks if the current user has admin privileges.
    """
    check_privileges(current_user.username, role="admin")
    return render_template("/admin/users.html", current_user=current_user)


@admin.route("/admin/create_user", methods=["POST"])
@login_required
def create_user():
    """
    This route handles creating a new student. It retrieves the necessary data from the form,
    creates a new User_mgmt object, and saves it to the database.
    """
    check_privileges(current_user.username, role="admin")
    email = request.form.get("email")
    username = request.form.get("username")
    name = request.form.get("name")
    surname = request.form.get("surname")
    cdl = request.form.get("cdl")
    gender = request.form.get("gender")
    nationality = request.form.get("nationality")
    password = request.form.get("password")
    password2 = request.form.get("password2")
    user_type = request.form.get("type")

    user = User_mgmt.query.filter_by(email=email).first()

    if user:
        flash("Email address already exists")
        return redirect(request.referrer)

    if password != password2:
        flash("Passwords do not match")
        return redirect(request.referrer)

    # create a new user with the form data. Hash the password so the plaintext version isn't saved.
    new_user = User_mgmt(
        email=email,
        username=username,
        password=generate_password_hash(password, method="pbkdf2:sha256"),
        name=name,
        surname=surname,
        cdl=cdl,
        nationality=nationality,
        gender=gender,
        user_type=user_type,
        joined_on=int(time.time()),
    )
    db.session.add(new_user)
    db.session.commit()
    return dashboard()


@admin.route("/admin/delete_user/<int:uid>")
@login_required
def delete_user(uid):
    """
    This route handles deleting a student. It retrieves the user by ID,
    deletes it from the database, and commits the changes.
    """
    check_privileges(current_user.username, role="admin")
    user = User_mgmt.query.filter_by(id=uid).first()
    if user:
        db.session.delete(user)
        db.session.commit()
        flash("User deleted successfully")
    else:
        flash("User not found")

    return redirect(request.referrer)


@admin.route("/admin/users_data")
@login_required
def users_data():
    query = User_mgmt.query

    # search filter
    search = request.args.get("search")
    if search:
        query = query.filter(
            db.or_(
                User_mgmt.name.like(f"%{search}%"),
            )
        )
    total = query.count()

    # sorting
    sort = request.args.get("sort")
    if sort:
        order = []
        for s in sort.split(","):
            direction = s[0]
            name = s[1:]
            if name not in ["name", "surname", "gender", "user_type"]:
                name = "name"
            col = getattr(User_mgmt, name)
            if direction == "-":
                col = col.desc()
            order.append(col)
        if order:
            query = query.order_by(*order)

    # pagination
    start = request.args.get("start", type=int, default=-1)
    length = request.args.get("length", type=int, default=-1)
    if start != -1 and length != -1:
        query = query.offset(start).limit(length)

    # response
    res = query.all()

    return {
        "data": [{"id": pop.id, "name": pop.name, "surname": pop.surname, "gender": pop.gender, "user_type": pop.user_type} for pop in res],
        "total": total,
    }


@admin.route("/admin/theses")
@login_required
def theses():
    """
    This route renders the form for creating a new thesis. It checks if the current user has admin privileges.
    """
    check_privileges(current_user.username, role="admin")
    students = User_mgmt.query.filter_by(user_type="student").all()
    supervisors = User_mgmt.query.filter_by(user_type="supervisor").all()
    return render_template("/admin/theses.html", current_user=current_user,
                           students=students, supervisors=supervisors)


@admin.route("/admin/theses_data", methods=["GET", "POST"])
@login_required
def theses_data():
    check_privileges(current_user.username, role="admin")
    
    # Handle POST request for inline editing
    if request.method == "POST":
        data = request.get_json()
        thesis_id = data.get("id")
        
        thesis = Thesis.query.get_or_404(thesis_id)
        
        if "title" in data:
            thesis.title = data["title"]
        if "level" in data:
            thesis.level = data["level"]
            
        db.session.commit()
        return {"status": "success"}, 200
    
    # Handle GET request for table data
    Author = aliased(User_mgmt)

    stmt = (
        select(Thesis, Author)
        .outerjoin(Author, Thesis.author_id == Author.id)
    )

    # search filter
    search = request.args.get("search")
    if search:
        stmt = stmt.where(
            or_(
                Author.name.ilike(f"%{search}%"),
                Thesis.level.ilike(f"%{search}%"),
                Thesis.title.ilike(f"%{search}%"),
            )
        )

    # sorting
    sort = request.args.get("sort")
    if sort:
        order = []
        for s in sort.split(","):
            direction = s[0]
            name = s[1:]
            if name not in ["title", "level", "author_cd"]:
                continue
            col = getattr(Author, name, None)
            if col is not None:
                col = col.desc() if direction == "-" else col.asc()
                order.append(col)
        if order:
            stmt = stmt.order_by(*order)

    # total count (separate execution if paginated)
    total = db.session.execute(stmt).all()
    total_count = len(total)

    # pagination
    start = request.args.get("start", type=int, default=-1)
    length = request.args.get("length", type=int, default=-1)
    if start != -1 and length != -1:
        stmt = stmt.offset(start).limit(length)

    results = db.session.execute(stmt).all()

    return {
        "total": total_count,
        "data": [
            {
                "thesis_id": thesis.id,
                "title": thesis.title,
                "level": thesis.level,
                "author_cd": author.cdl if author else None,
                "assigned": "True" if author else "False",
            }
            for thesis, author in results
        ],
    }




@admin.route("/admin/create_thesis", methods=["POST"])
@login_required
def create_thesis():
    """
    This route handles creating a new thesis. It retrieves the necessary data from the form,
    creates a new Thesis object, and saves it to the database.
    """
    check_privileges(current_user.username, role="admin")
    title = request.form.get("title")
    description = request.form.get("description")
    student_id = request.form.get("student_id")
    supervisor_id = request.form.get("supervisor_id")
    level = request.form.get("level")
    status = "thesis accepted"

    if not title or not description:
        flash("All fields are required")
        return redirect(request.referrer)

    try:
        new_thesis = Thesis(
            title=title,
            description=description,
            author_id=int(student_id) if student_id != "" else None,
            frozen=False,
            level=level,
            created_at=int(time.time()),
        )
        db.session.add(new_thesis)
        db.session.commit()

        # Only create supervisor assignment if supervisor_id is provided
        if supervisor_id and supervisor_id.strip():
            thesis_supervisor = Thesis_Supervisor(
                thesis_id=new_thesis.id,
                supervisor_id=int(supervisor_id),
                assigned_at=int(time.time()),
            )
            db.session.add(thesis_supervisor)
            db.session.commit()

        # Update the thesis status
        new_status = Thesis_Status(
            thesis_id=new_thesis.id,
            status=status,
            updated_at=int(time.time()),
        )
        db.session.add(new_status)
        db.session.commit()

        flash("Thesis created successfully")
        return redirect(url_for("admin.theses"))
    except Exception as e:
        flash(f"Error creating thesis: {e}")
        return redirect(request.referrer)


@admin.route("/admin/update_thesis", methods=["POST"])
@login_required
def update_thesis():
    """
    This route handles updating an existing thesis. It retrieves the necessary data from the form,
    updates the Thesis object, and saves it to the database.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id") or request.json.get("id")
    title = request.form.get("title") or request.json.get("title")
    level = request.form.get("level") or request.json.get("level")
    description = request.form.get("description") or request.json.get("description")

    thesis = Thesis.query.get_or_404(thesis_id)
    
    if title:
        thesis.title = title
    if level:
        thesis.level = level  
    if description:
        thesis.description = description
        
    db.session.commit()
    
    if request.is_json:
        return {"status": "success"}, 200
    
    flash("Thesis updated successfully")
    return redirect(url_for("admin.theses"))


@admin.route("/admin/delete_thesis/<int:thesis_id>", methods=["DELETE"])
@login_required
def delete_thesis(thesis_id):
    """
    This route handles deleting a thesis by its ID. It retrieves the Thesis object,
    deletes it from the database, and redirects to the theses data page.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis = Thesis.query.get_or_404(thesis_id)
    
    # Delete related records first
    Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).delete()
    Thesis_Status.query.filter_by(thesis_id=thesis_id).delete()
    Thesis_Tag.query.filter_by(thesis_id=thesis_id).delete()
    Thesis_Update.query.filter_by(thesis_id=thesis_id).delete()
    Resource.query.filter_by(thesis_id=thesis_id).delete()
    
    db.session.delete(thesis)
    db.session.commit()
    
    return {"status": "success"}, 200


@admin.route("/admin/thesis/<int:thesis_id>")
@login_required
def thesis_detail(thesis_id):
    """
    This route displays the details of a specific thesis including all related information
    like supervisors, tags, updates, and allows for editing.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis = Thesis.query.get_or_404(thesis_id)
    author = User_mgmt.query.get(thesis.author_id) if thesis.author_id else None
    supervisors_rel = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).all()
    supervisors = [User_mgmt.query.get(rel.supervisor_id) for rel in supervisors_rel]
    status_history = Thesis_Status.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Status.updated_at.desc()).all()
    tags = Thesis_Tag.query.filter_by(thesis_id=thesis_id).all()
    updates = Thesis_Update.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Update.created_at.desc()).all()
    
    # Get all students and supervisors for reassignment
    students = User_mgmt.query.filter_by(user_type="student").all()
    all_supervisors = User_mgmt.query.filter_by(user_type="supervisor").all()
    
    return render_template("/admin/thesis_detail.html", 
                         current_user=current_user,
                         thesis=thesis,
                         author=author,
                         supervisors=supervisors,
                         status_history=status_history,
                         tags=tags,
                         updates=updates,
                         students=students,
                         all_supervisors=all_supervisors,
                         datetime=datetime)


@admin.route("/admin/assign_student", methods=["POST"])
@login_required
def assign_student():
    """
    This route handles assigning or reassigning a student to a thesis.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    student_id = request.form.get("student_id")
    
    thesis = Thesis.query.get_or_404(thesis_id)
    thesis.author_id = int(student_id) if student_id else None
    db.session.commit()
    
    flash("Student assignment updated successfully")
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/assign_supervisor", methods=["POST"])
@login_required
def assign_supervisor():
    """
    This route handles assigning a supervisor to a thesis.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    supervisor_id = request.form.get("supervisor_id")
    
    # Check if this supervisor is already assigned
    existing = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id, supervisor_id=supervisor_id).first()
    if not existing:
        new_assignment = Thesis_Supervisor(
            thesis_id=thesis_id,
            supervisor_id=supervisor_id,
            assigned_at=int(time.time())
        )
        db.session.add(new_assignment)
        db.session.commit()
        flash("Supervisor assigned successfully")
    else:
        flash("Supervisor is already assigned to this thesis")
    
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/remove_supervisor", methods=["POST"])
@login_required
def remove_supervisor():
    """
    This route handles removing a supervisor from a thesis.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    supervisor_id = request.form.get("supervisor_id")
    
    assignment = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id, supervisor_id=supervisor_id).first()
    if assignment:
        db.session.delete(assignment)
        db.session.commit()
        flash("Supervisor removed successfully")
    
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/add_thesis_tag", methods=["POST"])
@login_required
def add_thesis_tag():
    """
    This route handles adding tags to a thesis.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    tag = request.form.get("tag")
    
    if tag and thesis_id:
        # Check if tag already exists
        existing_tag = Thesis_Tag.query.filter_by(thesis_id=thesis_id, tag=tag).first()
        if not existing_tag:
            new_tag = Thesis_Tag(
                thesis_id=thesis_id,
                tag=tag
            )
            db.session.add(new_tag)
            db.session.commit()
            flash("Tag added successfully")
        else:
            flash("Tag already exists")
    
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/remove_thesis_tag", methods=["POST"])
@login_required
def remove_thesis_tag():
    """
    This route handles removing tags from a thesis.
    """
    check_privileges(current_user.username, role="admin")
    
    tag_id = request.form.get("tag_id")
    thesis_id = request.form.get("thesis_id")
    
    tag = Thesis_Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()
    
    flash("Tag removed successfully")
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/archive_thesis", methods=["POST"])
@login_required
def archive_thesis():
    """
    This route handles archiving/unarchiving a thesis using the frozen field.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    action = request.form.get("action")  # "archive" or "unarchive"
    
    thesis = Thesis.query.get_or_404(thesis_id)
    thesis.frozen = (action == "archive")
    db.session.commit()
    
    status_text = "archived" if thesis.frozen else "unarchived"
    flash(f"Thesis {status_text} successfully")
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


