from flask_login import UserMixin

from . import db


class User_mgmt(UserMixin, db.Model):
    __tablename__ = "user_mgmt"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(15))
    surname = db.Column(db.String(15))
    cdl = db.Column(db.String(15))
    email = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)
    user_type = db.Column(db.String(10), nullable=False, default="student")
    joined_on = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), default=None)
    nationality = db.Column(db.String(15), default=None)

    thesis = db.relationship("Thesis", backref="author", lazy=True)


class Thesis(db.Model):
    __tablename__ = "thesis"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=True)
    frozen = db.Column(db.Boolean, default=False)
    level = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.Integer, nullable=False)


class Thesis_Status(db.Model):
    __tablename__ = "thesis_status"
    id = db.Column(db.Integer, primary_key=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey("thesis.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    updated_at = db.Column(db.Integer, nullable=False)

    thesis = db.relationship("Thesis", backref="status", lazy=True)


class Thesis_Supervisor(db.Model):
    __tablename__ = "thesis_supervisor"
    id = db.Column(db.Integer, primary_key=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey("thesis.id"), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    assigned_at = db.Column(db.Integer, nullable=False)

    thesis = db.relationship("Thesis", backref="supervisors", lazy=True)
    supervisor = db.relationship("User_mgmt", backref="supervised_theses", lazy=True)


class Thesis_Tag(db.Model):
    __tablename__ = "thesis_tag"
    id = db.Column(db.Integer, primary_key=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey("thesis.id"), nullable=False)
    tag = db.Column(db.String(50), nullable=False)
    thesis = db.relationship("Thesis", backref="tags", lazy=True)


class Update_Tag(db.Model):
    __tablename__ = "update_tag"
    id = db.Column(db.Integer, primary_key=True)
    update_id = db.Column(db.Integer, db.ForeignKey("thesis_update.id"), nullable=False)
    tag = db.Column(db.String(50), nullable=False)
    frozen = db.Column(db.Boolean, default=False)
    update = db.relationship("Thesis_Update", backref="tags", lazy=True)


class Thesis_Update(db.Model):
    __tablename__ = "thesis_update"
    id = db.Column(db.Integer, primary_key=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey("thesis.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    update_type = db.Column(db.String(20), nullable=False)  # e.g., "progress", "feedback"
    parent_id = db.Column(db.Integer, db.ForeignKey("thesis_update.id"), nullable=True, default=None)  # For threaded updates
    status = db.Column(db.String(20), nullable=False, default="active")  # e.g., "active", "frozen", "archived"
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.Integer, nullable=False)


class Resource(db.Model):
    __tablename__ = "resource"
    id = db.Column(db.Integer, primary_key=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey("thesis.id"), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False)  # e.g., "document", "link"
    resource_url = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.Integer, nullable=False)

    thesis = db.relationship("Thesis", backref="resources", lazy=True)


class Thesis_Objective(db.Model):
    __tablename__ = "thesis_objective"
    id = db.Column(db.Integer, primary_key=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey("thesis.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")  # e.g., "active", "frozen", "archived"
    frozen = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.Integer, nullable=False)

    thesis = db.relationship("Thesis", backref="objectives", lazy=True)
    author = db.relationship("User_mgmt", backref="objectives", lazy=True)


class Thesis_Hypothesis(db.Model):
    __tablename__ = "thesis_hypothesis"
    id = db.Column(db.Integer, primary_key=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey("thesis.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")  # e.g., "active", "frozen", "archived"
    frozen = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.Integer, nullable=False)

    thesis = db.relationship("Thesis", backref="hypotheses", lazy=True)
    author = db.relationship("User_mgmt", backref="hypotheses", lazy=True)


class Todo(db.Model):
    __tablename__ = "todo"
    id = db.Column(db.Integer, primary_key=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey("thesis.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending")  # "pending", "completed", "cancelled"
    priority = db.Column(db.String(10), nullable=False, default="medium")  # "low", "medium", "high"
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=True)  # Can be assigned to student or supervisor
    due_date = db.Column(db.Integer, nullable=True)  # Unix timestamp
    completed_at = db.Column(db.Integer, nullable=True)  # Unix timestamp when marked complete
    created_at = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.Integer, nullable=False)

    thesis = db.relationship("Thesis", backref="todos", lazy=True)
    author = db.relationship("User_mgmt", foreign_keys=[author_id], backref="created_todos", lazy=True)
    assigned_to = db.relationship("User_mgmt", foreign_keys=[assigned_to_id], backref="assigned_todos", lazy=True)