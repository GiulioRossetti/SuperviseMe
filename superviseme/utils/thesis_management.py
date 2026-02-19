"""
Thesis domain operations shared across role routes.
"""

from superviseme import db
from superviseme.models import (
    MeetingNote,
    MeetingNoteReference,
    Notification,
    Resource,
    Thesis,
    Thesis_Hypothesis,
    Thesis_Objective,
    Thesis_Status,
    Thesis_Supervisor,
    Thesis_Tag,
    Thesis_Update,
    Todo,
    Todo_Reference,
    Update_Tag,
)


def delete_thesis_with_dependencies(thesis_id):
    """
    Delete a thesis and all dependent records that are not handled via DB-level cascade.

    Returns:
        tuple[bool, str | None]: (success, error_message)
    """
    thesis = Thesis.query.get(thesis_id)
    if not thesis:
        return False, "Thesis not found"

    try:
        # Collect IDs first to safely clean cross-reference tables.
        update_ids = [
            row[0]
            for row in db.session.query(Thesis_Update.id).filter_by(thesis_id=thesis_id).all()
        ]
        todo_ids = [
            row[0]
            for row in db.session.query(Todo.id).filter_by(thesis_id=thesis_id).all()
        ]
        meeting_note_ids = [
            row[0]
            for row in db.session.query(MeetingNote.id).filter_by(thesis_id=thesis_id).all()
        ]

        if update_ids:
            Update_Tag.query.filter(Update_Tag.update_id.in_(update_ids)).delete(
                synchronize_session=False
            )
            Todo_Reference.query.filter(Todo_Reference.update_id.in_(update_ids)).delete(
                synchronize_session=False
            )

        if todo_ids:
            Todo_Reference.query.filter(Todo_Reference.todo_id.in_(todo_ids)).delete(
                synchronize_session=False
            )
            MeetingNoteReference.query.filter(
                MeetingNoteReference.todo_id.in_(todo_ids)
            ).delete(synchronize_session=False)

        if meeting_note_ids:
            MeetingNoteReference.query.filter(
                MeetingNoteReference.meeting_note_id.in_(meeting_note_ids)
            ).delete(synchronize_session=False)

        Notification.query.filter_by(thesis_id=thesis_id).delete(synchronize_session=False)
        Thesis_Status.query.filter_by(thesis_id=thesis_id).delete(synchronize_session=False)
        Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).delete(
            synchronize_session=False
        )
        Thesis_Tag.query.filter_by(thesis_id=thesis_id).delete(synchronize_session=False)
        Resource.query.filter_by(thesis_id=thesis_id).delete(synchronize_session=False)
        Thesis_Objective.query.filter_by(thesis_id=thesis_id).delete(
            synchronize_session=False
        )
        Thesis_Hypothesis.query.filter_by(thesis_id=thesis_id).delete(
            synchronize_session=False
        )
        MeetingNote.query.filter_by(thesis_id=thesis_id).delete(synchronize_session=False)
        Todo.query.filter_by(thesis_id=thesis_id).delete(synchronize_session=False)
        Thesis_Update.query.filter_by(thesis_id=thesis_id).delete(synchronize_session=False)

        db.session.delete(thesis)
        return True, None
    except Exception as e:  # pragma: no cover - defensive path
        db.session.rollback()
        return False, str(e)
