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
    last_activity = db.Column(db.Integer, nullable=True)  # Track last activity timestamp
    last_activity_location = db.Column(db.String(100), nullable=True)  # Track where they were last active
    
    # Telegram notification settings
    telegram_user_id = db.Column(db.String(50), nullable=True)  # Telegram user ID for bot notifications
    telegram_enabled = db.Column(db.Boolean, default=False, nullable=False)  # Enable/disable Telegram notifications
    telegram_notification_types = db.Column(db.Text, nullable=True)  # JSON string of enabled notification types

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


class Todo_Reference(db.Model):
    __tablename__ = "todo_reference"
    id = db.Column(db.Integer, primary_key=True)
    update_id = db.Column(db.Integer, db.ForeignKey("thesis_update.id"), nullable=False)
    todo_id = db.Column(db.Integer, db.ForeignKey("todo.id"), nullable=False)
    created_at = db.Column(db.Integer, nullable=False)
    
    update = db.relationship("Thesis_Update", backref="todo_references", lazy=True)
    todo = db.relationship("Todo", backref="update_references", lazy=True)


class Notification(db.Model):
    __tablename__ = "notification"
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)  # Who performed the action
    thesis_id = db.Column(db.Integer, db.ForeignKey("thesis.id"), nullable=True)  # Related thesis if applicable
    notification_type = db.Column(db.String(50), nullable=False)  # e.g., "new_update", "new_feedback", "new_todo"
    title = db.Column(db.String(200), nullable=False)  # Short description
    message = db.Column(db.Text, nullable=False)  # Detailed message
    action_url = db.Column(db.String(200), nullable=True)  # URL to the relevant page
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.Integer, nullable=False)
    
    # Telegram notification tracking
    telegram_sent = db.Column(db.Boolean, default=False, nullable=False)  # Track if Telegram notification was sent
    telegram_sent_at = db.Column(db.Integer, nullable=True)  # When Telegram notification was sent
    
    # Relationships
    recipient = db.relationship("User_mgmt", foreign_keys=[recipient_id], backref="received_notifications", lazy=True)
    actor = db.relationship("User_mgmt", foreign_keys=[actor_id], backref="sent_notifications", lazy=True)
    thesis = db.relationship("Thesis", backref="notifications", lazy=True)


class MeetingNote(db.Model):
    __tablename__ = "meeting_note"
    id = db.Column(db.Integer, primary_key=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey("thesis.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # Markdown content
    created_at = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.Integer, nullable=False)
    
    thesis = db.relationship("Thesis", backref="meeting_notes", lazy=True)
    author = db.relationship("User_mgmt", backref="authored_meeting_notes", lazy=True)


class MeetingNoteReference(db.Model):
    __tablename__ = "meeting_note_reference"
    id = db.Column(db.Integer, primary_key=True)
    meeting_note_id = db.Column(db.Integer, db.ForeignKey("meeting_note.id"), nullable=False)
    todo_id = db.Column(db.Integer, db.ForeignKey("todo.id"), nullable=False)
    created_at = db.Column(db.Integer, nullable=False)
    
    meeting_note = db.relationship("MeetingNote", backref="todo_references", lazy=True)
    todo = db.relationship("Todo", backref="meeting_note_references", lazy=True)


class TelegramBotConfig(db.Model):
    __tablename__ = "telegram_bot_config"
    id = db.Column(db.Integer, primary_key=True)
    bot_token = db.Column(db.String(200), nullable=False)  # Telegram bot token
    bot_username = db.Column(db.String(100), nullable=False)  # Bot username for display
    webhook_url = db.Column(db.String(500), nullable=True)  # Webhook URL if using webhooks
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # Enable/disable bot
    notification_types = db.Column(db.Text, nullable=False)  # JSON string of enabled notification types
    frequency_settings = db.Column(db.Text, nullable=True)  # JSON string of frequency settings (immediate, digest, etc.)


class ResearchProject(db.Model):
    __tablename__ = "research_project"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    researcher_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    frozen = db.Column(db.Boolean, default=False)
    level = db.Column(db.Text, nullable=True)  # e.g., "research", "pilot", "full-scale"
    created_at = db.Column(db.Integer, nullable=False)

    researcher = db.relationship("User_mgmt", backref="research_projects", lazy=True)


class ResearchProject_Collaborator(db.Model):
    __tablename__ = "research_project_collaborator"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), nullable=False)
    collaborator_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="collaborator")  # collaborator, co-investigator, etc.
    added_at = db.Column(db.Integer, nullable=False)

    project = db.relationship("ResearchProject", backref="collaborators", lazy=True)
    collaborator = db.relationship("User_mgmt", backref="collaborated_projects", lazy=True)


class Supervisor_Role(db.Model):
    __tablename__ = "supervisor_role"
    id = db.Column(db.Integer, primary_key=True)
    researcher_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    granted_by = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    granted_at = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    researcher = db.relationship("User_mgmt", foreign_keys=[researcher_id], backref="supervisor_roles", lazy=True)
    granter = db.relationship("User_mgmt", foreign_keys=[granted_by], backref="granted_supervisor_roles", lazy=True)
    created_at = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.Integer, nullable=False)


class ResearchProject_Status(db.Model):
    __tablename__ = "research_project_status"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    updated_at = db.Column(db.Integer, nullable=False)

    project = db.relationship("ResearchProject", backref="status_history", lazy=True)


class ResearchProject_Update(db.Model):
    __tablename__ = "research_project_update"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    update_type = db.Column(db.String(20), nullable=False)  # e.g., "progress", "feedback"
    parent_id = db.Column(db.Integer, db.ForeignKey("research_project_update.id"), nullable=True, default=None)  # For threaded updates
    status = db.Column(db.String(20), nullable=False, default="active")  # e.g., "active", "frozen", "archived"
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.Integer, nullable=False)

    project = db.relationship("ResearchProject", backref="updates", lazy=True)
    author = db.relationship("User_mgmt", backref="project_updates", lazy=True)


class ResearchProject_Resource(db.Model):
    __tablename__ = "research_project_resource"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False)  # e.g., "document", "link"
    resource_url = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.Integer, nullable=False)

    project = db.relationship("ResearchProject", backref="resources", lazy=True)


class ResearchProject_Objective(db.Model):
    __tablename__ = "research_project_objective"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")  # e.g., "active", "frozen", "archived"
    frozen = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.Integer, nullable=False)

    project = db.relationship("ResearchProject", backref="objectives", lazy=True)
    author = db.relationship("User_mgmt", backref="project_objectives", lazy=True)


class ResearchProject_Hypothesis(db.Model):
    __tablename__ = "research_project_hypothesis"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")  # e.g., "active", "frozen", "archived"
    frozen = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.Integer, nullable=False)

    project = db.relationship("ResearchProject", backref="hypotheses", lazy=True)
    author = db.relationship("User_mgmt", backref="project_hypotheses", lazy=True)


class ResearchProject_Todo(db.Model):
    __tablename__ = "research_project_todo"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending")  # "pending", "completed", "cancelled"
    priority = db.Column(db.String(10), nullable=False, default="medium")  # "low", "medium", "high"
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=True)  # Can be assigned to any collaborator
    due_date = db.Column(db.Integer, nullable=True)  # Unix timestamp
    completed_at = db.Column(db.Integer, nullable=True)  # Unix timestamp when marked complete
    created_at = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.Integer, nullable=False)

    project = db.relationship("ResearchProject", backref="todos", lazy=True)
    author = db.relationship("User_mgmt", foreign_keys=[author_id], backref="created_project_todos", lazy=True)
    assigned_to = db.relationship("User_mgmt", foreign_keys=[assigned_to_id], backref="assigned_project_todos", lazy=True)


class ResearchProject_MeetingNote(db.Model):
    __tablename__ = "research_project_meeting_note"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("research_project.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user_mgmt.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # Markdown content
    created_at = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.Integer, nullable=False)
    
    project = db.relationship("ResearchProject", backref="meeting_notes", lazy=True)
    author = db.relationship("User_mgmt", backref="authored_project_meeting_notes", lazy=True)


class ResearchProject_TodoReference(db.Model):
    __tablename__ = "research_project_todo_reference"
    id = db.Column(db.Integer, primary_key=True)
    update_id = db.Column(db.Integer, db.ForeignKey("research_project_update.id"), nullable=False)
    todo_id = db.Column(db.Integer, db.ForeignKey("research_project_todo.id"), nullable=False)
    created_at = db.Column(db.Integer, nullable=False)
    
    update = db.relationship("ResearchProject_Update", backref="todo_references", lazy=True)
    todo = db.relationship("ResearchProject_Todo", backref="update_references", lazy=True)


class ResearchProject_MeetingNoteReference(db.Model):
    __tablename__ = "research_project_meeting_note_reference"
    id = db.Column(db.Integer, primary_key=True)
    meeting_note_id = db.Column(db.Integer, db.ForeignKey("research_project_meeting_note.id"), nullable=False)
    todo_id = db.Column(db.Integer, db.ForeignKey("research_project_todo.id"), nullable=False)
    created_at = db.Column(db.Integer, nullable=False)
    
    meeting_note = db.relationship("ResearchProject_MeetingNote", backref="todo_references", lazy=True)
    todo = db.relationship("ResearchProject_Todo", backref="project_meeting_note_references", lazy=True)