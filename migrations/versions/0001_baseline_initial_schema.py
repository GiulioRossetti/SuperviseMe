"""baseline: initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_mgmt',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=15), nullable=True),
        sa.Column('surname', sa.String(length=15), nullable=True),
        sa.Column('cdl', sa.String(length=15), nullable=True),
        sa.Column('email', sa.String(length=50), nullable=False),
        sa.Column('password', sa.String(length=80), nullable=False),
        sa.Column('user_type', sa.String(length=10), nullable=False),
        sa.Column('joined_on', sa.Integer(), nullable=False),
        sa.Column('gender', sa.String(length=10), nullable=True),
        sa.Column('nationality', sa.String(length=15), nullable=True),
        sa.Column('last_activity', sa.Integer(), nullable=True),
        sa.Column('last_activity_location', sa.String(length=100), nullable=True),
        sa.Column('telegram_user_id', sa.String(length=50), nullable=True),
        sa.Column('telegram_enabled', sa.Boolean(), nullable=False),
        sa.Column('telegram_notification_types', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user_mgmt')),
        sa.UniqueConstraint('email', name=op.f('uq_user_mgmt_email')),
        sa.UniqueConstraint('username', name=op.f('uq_user_mgmt_username')),
    )
    op.create_table(
        'telegram_bot_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bot_token', sa.String(length=200), nullable=False),
        sa.Column('bot_username', sa.String(length=100), nullable=False),
        sa.Column('webhook_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('notification_types', sa.Text(), nullable=False),
        sa.Column('frequency_settings', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_telegram_bot_config')),
    )
    op.create_table(
        'thesis',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('frozen', sa.Boolean(), nullable=True),
        sa.Column('level', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_thesis_author_id_user_mgmt')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_thesis')),
    )
    op.create_table(
        'research_project',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('researcher_id', sa.Integer(), nullable=False),
        sa.Column('frozen', sa.Boolean(), nullable=True),
        sa.Column('level', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['researcher_id'], ['user_mgmt.id'],
                                name=op.f('fk_research_project_researcher_id_user_mgmt')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project')),
    )
    op.create_table(
        'notification',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
        sa.Column('thesis_id', sa.Integer(), nullable=True),
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('action_url', sa.String(length=200), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('telegram_sent', sa.Boolean(), nullable=False),
        sa.Column('telegram_sent_at', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['actor_id'], ['user_mgmt.id'],
                                name=op.f('fk_notification_actor_id_user_mgmt')),
        sa.ForeignKeyConstraint(['recipient_id'], ['user_mgmt.id'],
                                name=op.f('fk_notification_recipient_id_user_mgmt')),
        sa.ForeignKeyConstraint(['thesis_id'], ['thesis.id'],
                                name=op.f('fk_notification_thesis_id_thesis')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notification')),
    )
    op.create_table(
        'thesis_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thesis_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['thesis_id'], ['thesis.id'],
                                name=op.f('fk_thesis_status_thesis_id_thesis')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_thesis_status')),
    )
    op.create_table(
        'thesis_supervisor',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thesis_id', sa.Integer(), nullable=False),
        sa.Column('supervisor_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['supervisor_id'], ['user_mgmt.id'],
                                name=op.f('fk_thesis_supervisor_supervisor_id_user_mgmt')),
        sa.ForeignKeyConstraint(['thesis_id'], ['thesis.id'],
                                name=op.f('fk_thesis_supervisor_thesis_id_thesis')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_thesis_supervisor')),
    )
    op.create_table(
        'thesis_tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thesis_id', sa.Integer(), nullable=False),
        sa.Column('tag', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['thesis_id'], ['thesis.id'],
                                name=op.f('fk_thesis_tag_thesis_id_thesis')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_thesis_tag')),
    )
    op.create_table(
        'thesis_update',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thesis_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('update_type', sa.String(length=20), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_thesis_update_author_id_user_mgmt')),
        sa.ForeignKeyConstraint(['parent_id'], ['thesis_update.id'],
                                name=op.f('fk_thesis_update_parent_id_thesis_update')),
        sa.ForeignKeyConstraint(['thesis_id'], ['thesis.id'],
                                name=op.f('fk_thesis_update_thesis_id_thesis')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_thesis_update')),
    )
    op.create_table(
        'resource',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thesis_id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_url', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['thesis_id'], ['thesis.id'],
                                name=op.f('fk_resource_thesis_id_thesis')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_resource')),
    )
    op.create_table(
        'thesis_objective',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thesis_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('frozen', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_thesis_objective_author_id_user_mgmt')),
        sa.ForeignKeyConstraint(['thesis_id'], ['thesis.id'],
                                name=op.f('fk_thesis_objective_thesis_id_thesis')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_thesis_objective')),
    )
    op.create_table(
        'thesis_hypothesis',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thesis_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('frozen', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_thesis_hypothesis_author_id_user_mgmt')),
        sa.ForeignKeyConstraint(['thesis_id'], ['thesis.id'],
                                name=op.f('fk_thesis_hypothesis_thesis_id_thesis')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_thesis_hypothesis')),
    )
    op.create_table(
        'todo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thesis_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('priority', sa.String(length=10), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), nullable=True),
        sa.Column('due_date', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['user_mgmt.id'],
                                name=op.f('fk_todo_assigned_to_id_user_mgmt')),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_todo_author_id_user_mgmt')),
        sa.ForeignKeyConstraint(['thesis_id'], ['thesis.id'],
                                name=op.f('fk_todo_thesis_id_thesis')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_todo')),
    )
    op.create_table(
        'update_tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('update_id', sa.Integer(), nullable=False),
        sa.Column('tag', sa.String(length=50), nullable=False),
        sa.Column('frozen', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['update_id'], ['thesis_update.id'],
                                name=op.f('fk_update_tag_update_id_thesis_update')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_update_tag')),
    )
    op.create_table(
        'todo_reference',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('update_id', sa.Integer(), nullable=False),
        sa.Column('todo_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['todo_id'], ['todo.id'],
                                name=op.f('fk_todo_reference_todo_id_todo')),
        sa.ForeignKeyConstraint(['update_id'], ['thesis_update.id'],
                                name=op.f('fk_todo_reference_update_id_thesis_update')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_todo_reference')),
    )
    op.create_table(
        'meeting_note',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thesis_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_meeting_note_author_id_user_mgmt')),
        sa.ForeignKeyConstraint(['thesis_id'], ['thesis.id'],
                                name=op.f('fk_meeting_note_thesis_id_thesis')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_meeting_note')),
    )
    op.create_table(
        'meeting_note_reference',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_note_id', sa.Integer(), nullable=False),
        sa.Column('todo_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['meeting_note_id'], ['meeting_note.id'],
                                name=op.f('fk_meeting_note_reference_meeting_note_id_meeting_note')),
        sa.ForeignKeyConstraint(['todo_id'], ['todo.id'],
                                name=op.f('fk_meeting_note_reference_todo_id_todo')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_meeting_note_reference')),
    )
    op.create_table(
        'supervisor_role',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('researcher_id', sa.Integer(), nullable=False),
        sa.Column('granted_by', sa.Integer(), nullable=False),
        sa.Column('granted_at', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['granted_by'], ['user_mgmt.id'],
                                name=op.f('fk_supervisor_role_granted_by_user_mgmt')),
        sa.ForeignKeyConstraint(['researcher_id'], ['user_mgmt.id'],
                                name=op.f('fk_supervisor_role_researcher_id_user_mgmt')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_supervisor_role')),
    )
    op.create_table(
        'research_project_collaborator',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('collaborator_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('added_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['collaborator_id'], ['user_mgmt.id'],
                                name=op.f('fk_research_project_collaborator_collaborator_id_user_mgmt')),
        sa.ForeignKeyConstraint(['project_id'], ['research_project.id'],
                                name=op.f('fk_research_project_collaborator_project_id_research_project')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project_collaborator')),
    )
    op.create_table(
        'research_project_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['research_project.id'],
                                name=op.f('fk_research_project_status_project_id_research_project')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project_status')),
    )
    op.create_table(
        'research_project_update',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('update_type', sa.String(length=20), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_research_project_update_author_id_user_mgmt')),
        sa.ForeignKeyConstraint(['parent_id'], ['research_project_update.id'],
                                name=op.f('fk_research_project_update_parent_id_research_project_update')),
        sa.ForeignKeyConstraint(['project_id'], ['research_project.id'],
                                name=op.f('fk_research_project_update_project_id_research_project')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project_update')),
    )
    op.create_table(
        'research_project_resource',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_url', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['research_project.id'],
                                name=op.f('fk_research_project_resource_project_id_research_project')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project_resource')),
    )
    op.create_table(
        'research_project_objective',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('frozen', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_research_project_objective_author_id_user_mgmt')),
        sa.ForeignKeyConstraint(['project_id'], ['research_project.id'],
                                name=op.f('fk_research_project_objective_project_id_research_project')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project_objective')),
    )
    op.create_table(
        'research_project_hypothesis',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('frozen', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_research_project_hypothesis_author_id_user_mgmt')),
        sa.ForeignKeyConstraint(['project_id'], ['research_project.id'],
                                name=op.f('fk_research_project_hypothesis_project_id_research_project')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project_hypothesis')),
    )
    op.create_table(
        'research_project_todo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('priority', sa.String(length=10), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), nullable=True),
        sa.Column('due_date', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['user_mgmt.id'],
                                name=op.f('fk_research_project_todo_assigned_to_id_user_mgmt')),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_research_project_todo_author_id_user_mgmt')),
        sa.ForeignKeyConstraint(['project_id'], ['research_project.id'],
                                name=op.f('fk_research_project_todo_project_id_research_project')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project_todo')),
    )
    op.create_table(
        'research_project_meeting_note',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user_mgmt.id'],
                                name=op.f('fk_research_project_meeting_note_author_id_user_mgmt')),
        sa.ForeignKeyConstraint(['project_id'], ['research_project.id'],
                                name=op.f('fk_research_project_meeting_note_project_id_research_project')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project_meeting_note')),
    )
    op.create_table(
        'research_project_todo_reference',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('update_id', sa.Integer(), nullable=False),
        sa.Column('todo_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['todo_id'], ['research_project_todo.id'],
                                name=op.f('fk_research_project_todo_reference_todo_id_research_project_todo')),
        sa.ForeignKeyConstraint(['update_id'], ['research_project_update.id'],
                                name=op.f('fk_research_project_todo_reference_update_id_research_project_update')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project_todo_reference')),
    )
    op.create_table(
        'research_project_meeting_note_reference',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_note_id', sa.Integer(), nullable=False),
        sa.Column('todo_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['meeting_note_id'], ['research_project_meeting_note.id'],
                                name=op.f('fk_research_project_meeting_note_reference_meeting_note_id_research_project_meeting_note')),
        sa.ForeignKeyConstraint(['todo_id'], ['research_project_todo.id'],
                                name=op.f('fk_research_project_meeting_note_reference_todo_id_research_project_todo')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_research_project_meeting_note_reference')),
    )


def downgrade():
    op.drop_table('research_project_meeting_note_reference')
    op.drop_table('research_project_todo_reference')
    op.drop_table('research_project_meeting_note')
    op.drop_table('research_project_todo')
    op.drop_table('research_project_hypothesis')
    op.drop_table('research_project_objective')
    op.drop_table('research_project_resource')
    op.drop_table('research_project_update')
    op.drop_table('research_project_status')
    op.drop_table('research_project_collaborator')
    op.drop_table('supervisor_role')
    op.drop_table('meeting_note_reference')
    op.drop_table('meeting_note')
    op.drop_table('todo_reference')
    op.drop_table('update_tag')
    op.drop_table('todo')
    op.drop_table('thesis_hypothesis')
    op.drop_table('thesis_objective')
    op.drop_table('resource')
    op.drop_table('thesis_update')
    op.drop_table('thesis_tag')
    op.drop_table('thesis_supervisor')
    op.drop_table('thesis_status')
    op.drop_table('notification')
    op.drop_table('thesis')
    op.drop_table('research_project')
    op.drop_table('telegram_bot_config')
    op.drop_table('user_mgmt')
